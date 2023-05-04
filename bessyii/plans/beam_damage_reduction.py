from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp

from functools import partial
from bluesky.plan_stubs import checkpoint, abs_set, rel_set,wait, trigger_and_read, sleep
import numpy as np

from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)

from ophyd import Signal

import sys
import inspect
from itertools import chain, zip_longest
from functools import partial
import collections
from collections import defaultdict
import time

import numpy as np
try:
    # cytools is a drop-in replacement for toolz, implemented in Cython
    from cytools import partition
except ImportError:
    from toolz import partition

from bluesky import plan_patterns

from bluesky.plans import scan_nd, scan
from bluesky import utils
from bluesky.utils import Msg

from bluesky import preprocessors as bpp
from bluesky import plan_stubs as bps
from bessyii.plans.flying import flyscan
    
def beam_reduction_xas_flyer_line(detectors,flyer,energies,motor,start_pos,step_size,num,sleep_time,*,shutter=None, mono_vel=0.2,md=None):

    """
    move a motor from a start position in a line at num points, with step_size increment
    at each point open the valve and perform a flyscan at energies defined in energies. At each point set the Keithley range of the first kth in detectors list


    Parameters
    ----------
    detectors : list
        list of 'readable' objects. Assume that the first device in the list is the kth we want to change the range of
    flyer :
        Object of FlyerDevice type
    energies : list of tuples
        start, stop, kth range
        e.g [(500,510,'20 nA'),(800,820, '200 nA’)] 
    mono_vel: monochromator velocity 
    motor: positioner
        the motor we will use to scan the position of the sample/light
    start_pos: float
        the position we want to move the motor to at the start of each line
    step_size: float
        how much should we move the motor at each step. The sign will dictate direction
    num: int
        how many steps should we have in one line? must be a multiple of number of energy ranges
    shutter: PVPositioner
        A positioner that we can move to open and close the beam
    sleep_time: int
        the time in seconds to wait between moving each 
    md : dict, optional
        metadata

    """

    md = md or {}
    
    
    if num % len(energies) != 0:
        raise ValueError("number of steps is not a multiple of the number of energy ranges")
    

    #close the valve:
    print(f"closing {shutter.name}")
    yield from abs_set(shutter, shutter.close_value, wait=True)
    yield from checkpoint()
    
    #move the sample stage to the start position
    print(f"moving {motor.name} to {start_pos}")
    yield from abs_set(motor, start_pos, wait=True)
    
    
    for step in range(int(num/len(energies))):

        for energy in energies:
            #Set the keithley range
            print(f"setting {detectors[0].name} range to {energy[2]}")
            yield from abs_set(detectors[0].rnge, energy[2], wait=True)

            _md = {'i':step}
            _md.update(md or {})

            #move the energy to the start with the valve still closed
            print(f"moving {flyer.name} to {energy[0]}")
            yield from abs_set(flyer, energy[0], wait=True)

            #perform the scan, opening and closing the valve
            print("Starting flyscan")
            yield from flyscan(detectors,flyer,energy[0],energy[1],mono_vel,shutter=shutter,md=_md)
            
            #move the motors of the sample stage
            yield from rel_set(motor,step_size, wait=True)


        #sleep if we are not at the last step
        if step < num-1:
            yield from sleep(sleep_time)
            yield from checkpoint()

from bluesky.preprocessors import plan_mutator as plan_mangler

def valve_open_wrapper(plan, valve):

    """
    Open a valve before any trigger and read, and close it afterwards

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    valve : positioner with open and close values

    Yields
    ------
    msg : Msg
        messages from plan with set messages inserted
    """
    seen_group_list = []
    def insert_open_close(msg):
        

        if (msg.command == 'wait' and "set" in msg.kwargs['group']):

            return None, abs_set(valve, valve.open_value, wait=True)
            
        elif (msg.command == 'set' and msg.kwargs['group'] not in seen_group_list and msg.obj != valve):
            #Add it to the positioners to move
            #Msg('set', obj=SynAxis(prefix='', name='motor', read_attrs=['readback', 'setpoint'], configuration_attrs=['velocity', 'acceleration']), args=(1.6666666666666665,), kwargs={'group': 'set-6e4e36'}, run=None),
            grp = msg.kwargs['group']
            seen_group_list.append(grp)
            
            def abs_set_in_group(obj, val, group):
                ret = yield Msg('set', obj, val, group=group)
                return ret
                
            
            return None, abs_set_in_group(valve, valve.close_value, group=grp)
        
        elif (msg.command == 'close_run'):
             return None, abs_set(valve, valve.close_value, wait=True)
            

        else:
            return None, None
           
    return (yield from plan_mangler(plan, insert_open_close))

    
def beam_reduction_xas_stepwise_line(detectors,mono,energies,motor,start_pos,step_size,num,sleep_time,*,shutter=None,md=None):

    """
    move a motor from a start position in a line at num points, with step_size increment
    at each point open the valve and perform stepwise scans at energies defined in energies. At each point set the Keithley range of the first kth in detectors list
    open and close the valve around each stepwise point

    Parameters
    ----------
    detectors : list
        list of 'readable' objects. Assume that the first device in the list is the kth we want to change the range of
    mono :
        Object of FlyerDevice type
    energies : list of tuples
        start, stop, step_size, kth range
        e.g [(500,510,0.25,'20 nA'),(800,820,0.25 '200 nA’)] 
    motor: positioner
        the motor we will use to scan the position of the sample/light
    start_pos: float
        the position we want to move the motor to at the start of each line
    step_size: float
        how much should we move the motor at each step. The sign will dictate direction
    num: int
        how many steps should we have in one line? must be a multiple of number of energy ranges
    shutter: PVPositioner (optional)
        A positioner that we can move to open and close the beam
    sleep_time: int
        the time in seconds to wait between moving each 
    md : dict, optional
        metadata

    """

    md = md or {}
    
    
    if num % len(energies) != 0:
        raise ValueError("number of steps is not a multiple of the number of energy ranges")
    

    #close the valve:
    if shutter:
        yield from abs_set(shutter, shutter.close_value, wait=True)
        yield from checkpoint()
    
    #move the sample stage to the start position
    yield from abs_set(motor, start_pos, wait=True)
    
    
    for step in range(int(num/len(energies))):

        for energy in energies:
            #calculate num
            num = int((energy[1]-energy[0])/energy[2]+1)
            #Set the keithley range
            yield from abs_set(detectors[0].rnge, energy[3], wait=True)

            _md = {'i':step}
            _md.update(md or {})

            #move the energy to the start with the valve still closed
            yield from abs_set(mono, energy[0], wait=True)
            
            #perform the scan
            if shutter:
                yield from valve_open_wrapper(scan(detectors,mono,energy[0],energy[1],num,md=_md), shutter)
            else:
                yield from scan(detectors,mono,energy[0],energy[1],num,md=_md)

            #close the valve:
            
            if valve:
                yield from abs_set(shutter, shutter.close_value, wait=True)
                yield from checkpoint()
    
            #move the motors of the sample stage
            yield from rel_set(motor,step_size, wait=True)

        #sleep if we are not at the last step
        if step < num-1:
            yield from sleep(sleep_time)
            yield from checkpoint()

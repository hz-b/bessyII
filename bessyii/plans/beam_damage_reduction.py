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

def rad_flyscan(detectors, flyer, start=None, stop=None, vel =0.2, delay=0.2,valve=None,*, md=None):
    
    """
    count detectors while flying a flyer with start, stop, initial scan velocity, and the delay between det sample time

    The flyer object should implement the ophyd flyer device methods, although we don't use the collect method, instead we poll all of the detectors in the detectors list, as well as the parameters in the read_args of the flyer object.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    flyer :
        Object of FlyerDevice type
    start : float
        The start value fo the flyer
    stop : float
        The stop value of the flyer
    vel : float
        The initial velocity of the flyer; default is 0.2
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.2
    valve: PVPositioner
        A positioner that we can move to open and close the beam
    md : dict, optional
        metadata

    """
    
    # TODO
    # Add test that detectors is a list longer than 0
    
    #Add the flyer to the list of things we want to count
    detectors_list = detectors.append(flyer)
    
    
    #Define the motor metadata (important for plotting)
    motor = flyer
    md = md or {}

    del_req = delay

    if del_req < 0.2:
        
        raise ValueError("Sample rate too high.Delay must be >= 0.2 \n")

    flyer.velocity.put(vel)

    md_args = [repr(motor),start,stop,vel,del_req]
    x_fields = []
    x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))
    _md = {'detectors': [det.name for det in detectors],
           'motors': x_fields,
           'plan_args': {'detectors': list(map(repr, detectors)),
                         'motors' : flyer.name,
                         'start': start, 
                         'stop' : stop,
                         'vel': vel,
                         'delay': del_req,
                         'args':md_args
                         },

           'plan_name': 'flycount',
           'hints': {},
       }
    _md.update(md or {})
    
    # Deterime the name of the x axis for plotting from the flyer
    default_dimensions = [(x_fields, 'primary')]
    default_hints = {}
    
    # The following is left from the scan plan implementation, assumes multiple motors
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    # now add default_hints and override any hints from the original md (if
    # exists)
    
    _md['hints'] = default_hints
    _md.update(md)
  
    # Configure the flyer (but don't yet init or start)
    flyer.start_pos.put(start)
    flyer.end_pos.put(stop)
    
    # Init the run
    uid = yield from bps.open_run(_md)
    
    if valve:
        yield from abs_set(valve, 1, wait=True)
        yield from checkpoint()

    # Start the flyer and wait until it's reported that it's started
    yield from bps.kickoff(flyer, wait=True)

    # Get the status object that tells us when it's done
    complete_status = yield from bps.complete(flyer, wait=False)
    
    
    while not complete_status.done:

        yield Msg('checkpoint') # allows us to pause the run 
        yield from bps.one_shot(detectors) #triggers and reads everything in the detectors list
        yield Msg('sleep', None, del_req)

    if valve:
        yield from abs_set(valve, 0, wait=True)
        yield from checkpoint()
    
    yield from bps.close_run()
    return uid
    
    
def beam_reduction_xas_flyer_line(detectors,flyer,energies,motor,start_pos,step_size,num,valve,sleep_time,*,mono_vel=0.2,md=None):

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
    valve: PVPositioner
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
    yield from abs_set(valve, 0, wait=True)
    yield from checkpoint()
    
    #move the sample stage to the start position
    yield from abs_set(motor, start_pos, wait=True)
    
    
    for step in range(int(num/len(energies))):

        for energy in energies:
            #Set the keithley range
            yield from abs_set(detectors[0].rnge, energy[2], wait=True)

            _md = {'i':step}
            _md.update(md or {})

            #move the energy to the start with the valve still closed
            yield from abs_set(flyer, energy[0], wait=True)

            #perform the scan, opening and closing the valve
            yield from rad_flyscan(detectors,flyer,energy[0],energy[1],mono_vel,valve=valve,md=_md)
            
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
    valve : positioner
        valve to open

    Yields
    ------
    msg : Msg
        messages from plan with set messages inserted
    """
    seen_group_list = []
    def insert_open_close(msg):
        

        if (msg.command == 'wait' and "set" in msg.kwargs['group']):
            return None, abs_set(valve, 1, wait=True)
            
        elif (msg.command == 'set' and msg.kwargs['group'] not in seen_group_list and msg.obj != valve):
            #Add it to the positioners to move
            #Msg('set', obj=SynAxis(prefix='', name='motor', read_attrs=['readback', 'setpoint'], configuration_attrs=['velocity', 'acceleration']), args=(1.6666666666666665,), kwargs={'group': 'set-6e4e36'}, run=None),
            grp = msg.kwargs['group']
            seen_group_list.append(grp)
            
            def abs_set_in_group(obj, val, group):
                ret = yield Msg('set', obj, val, group=group)
                return ret
                
            
            return None, abs_set_in_group(valve, 0, group=grp)
        
        elif (msg.command == 'close_run'):
             return None, abs_set(valve, 0, wait=True)
            

        else:
            return None, None
            
    return (yield from plan_mangler(plan, insert_open_close))

    
def beam_reduction_xas_stepwise_line(detectors,mono,energies,motor,start_pos,step_size,num,sleep_time,*,valve=None,md=None):

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
    valve: PVPositioner (optional)
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
    if valve:
        yield from abs_set(valve, 0, wait=True)
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
            if valve:
                yield from valve_open_wrapper(scan(detectors,mono,energy[0],energy[1],num,md=_md),valve)
            else:
                yield from scan(detectors,mono,energy[0],energy[1],num,md=_md)

            #close the valve:
            
            if valve:
                yield from abs_set(valve, 0, wait=True)
                yield from checkpoint()
    
            #move the motors of the sample stage
            yield from rel_set(motor,step_size, wait=True)

        #sleep if we are not at the last step
        if step < num-1:
            yield from sleep(sleep_time)
            yield from checkpoint()

from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from functools import partial
import numpy as np

from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)

from ophyd import Signal

def flycount(detectors,flyer, *,delay=0.2,shutter=None, md=None):
    """
    read from detectors in a list while a flyer is running. Stop only when it completes

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    flyer : flyer object
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.2
    shutter : Device with open and close value attributes
        If defined, a shutter will be opened when the device complete's kickoff
    md : dict, optional
        metadata

    Notes
    -----

    """

    #Define the motor metadata (important for plotting)
    md = md or {}

    _md = {'detectors': [det.name for det in detectors],

           'plan_args': {'detectors': list(map(repr, detectors))},
           'flyer': flyer.name,
           'plan_name': 'flycount',
           'hints': {}
           }

    _md.update(md or {})
    
    
    _md['hints'].setdefault('dimensions', [(('time',), 'primary')])
    _md.update(md)

    
    # Init the run
    uid = yield from bps.open_run(_md)

    # Start the flyer and wait until it's reported that it's started
    yield from bps.kickoff(flyer, wait=True)

    # Get the status object that tells us when it's done
    complete_status = yield from bps.complete(flyer, wait=False)

    #Now open the shutter if it's defined
    if shutter:
        yield from bps.mov(shutter,shutter.open_value,wait=True)

    while not complete_status.done:

        yield Msg('checkpoint') # allows us to pause the run 
        yield from bps.one_shot(detectors) #triggers and reads everything in the detectors list
        yield Msg('sleep', None, delay)

    #Now close the shutter if it's defined
    if shutter:
        yield from bps.mov(shutter,shutter.close_value,wait=True)

    yield from bps.close_run()
    return uid




def flyscan(detectors, flyer, start=None, stop=None, vel =0.2, delay=0.1,shutter=None,*, md=None):
    
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
        The initial velocity of the flyer; default is 0.1
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.1
    shutter : Device with open and close value attributes
        If defined, a shutter will be opened when the device complete's kickoff
    md : dict, optional
        metadata

    """
    
    # TODO
    # Add test that detectors is a list longer than 0
    
    #Add the flyer to the list of things we want to count
    detectors_list = detectors + [flyer]
    
    
    #Define the motor metadata (important for plotting)
    motor = flyer
    md = md or {}

    del_req = delay

    if del_req < 0.1:
        
        raise ValueError("Sample rate too high.Delay must be >= 0.1 \n")

    yield from bps.configure(flyer,{"velocity":vel})

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

           'plan_name': 'flyscan',
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
    yield from bps.abs_set(flyer.start_pos,start)
    yield from bps.abs_set(flyer.end_pos,stop)
    return(yield from flycount(detectors_list,flyer,delay=del_req,shutter=shutter,md=_md))

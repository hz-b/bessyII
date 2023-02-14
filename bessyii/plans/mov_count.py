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

from ophyd.status import wait

from ophyd import Signal

def mov_count(detectors,motor,start, stop, *,vel=None,delay=0.2, md=None):
    """
    read from detectors in a list while a motor is moving. Stop only when it completes

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    motor: positioner
    start_pos: float
        The position to initially move the positioner to
    end_position: float
        The position to move to
    vel: float (optional)
        The velocity to set the motor to during the move. Set only if the motor has a velocity attribute
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.2
    md : dict, optional
        metadata

    Notes
    -----

    """

    #Define the motor metadata (important for plotting)
    md = md or {}
    x_fields = []
    x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))
    _md = {'detectors': [det.name for det in detectors],

           'plan_args': {'detectors': list(map(repr, detectors))},
           'motor': motor.name,
           'start': start,
           'stop': stop,
           'vel':vel,
           'plan_name': 'mov_count',
           'hints': {}
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

    #Add the flyer to the list of things we want to count
    detectors_list = detectors + [motor]
    
    # Init the run
    uid = yield from bps.open_run(_md)

    # Start the flyer and wait until it's reported that it's started
    yield from bps.mov(motor,start)

    #stash the device velocity
    if hasattr(motor, "velocity") and vel:
        initial_vel = motor.velocity.get()
        yield from bps.configure(motor, {"velocity":vel})

    # Get the status object that tells us when it's done
    complete_status = yield Msg('set', motor, stop)

    while not complete_status.done:

        yield Msg('checkpoint') # allows us to pause the run 
        yield from bps.one_shot(detectors_list) #triggers and reads everything in the detectors list
        yield Msg('sleep', None, delay)


    yield from bps.close_run()

    #reset the device velocity
    if hasattr(motor, "velocity") and vel:
        yield from bps.configure(motor, {"velocity":initial_vel})
    return uid

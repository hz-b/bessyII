from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from functools import partial
import numpy as np

from itertools import chain, zip_longest
from functools import partial
import collections
from collections import defaultdict
import time

import numpy as np
from toolz import partition


from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)

from ophyd import Signal

def mov_count(detectors,motor1, start_pos_1, stop_pos_1, motor2, start_pos_2, stop_pos_2,delay=0, md=None):
    """
    read from detectors in a list while 2 motors are moving. Stop only when they complete

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    motor1 : positioner
    start_pos_1 : float
    stop_pos_1 : float
    motor2 : positioner
    start_pos_2 : float
    stop_pos_2 : float
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.2
    md : dict, optional
        metadata

    Notes
    -----

    """

    motors_list = [motor1, motor2]


    #Define the motor metadata (important for plotting)
    md = md or {}
    x_fields = []
    for motor in motors_list:
        x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

    _md = {'detectors': [det.name for det in detectors],
           'plan_args': {'detectors': list(map(repr, detectors)),
                         'motors': list(map(repr,motors_list))
                        },
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
    detectors_list = detectors + motors_list
    
    # Init the run
    uid = yield from bps.open_run(_md)

    # Start the motors and wait until it's reported that it's done
    yield from bps.mov(motor1,start_pos_1, motor2, start_pos_2, group="start_move")
    yield from bps.wait("start_move")    

    # Get the status object that tells us when it's done
    complete_status1 = yield Msg('set', motor1, stop_pos_1)
    complete_status2 = yield Msg('set', motor2, stop_pos_2)

    while not complete_status1.done or not complete_status2.done:

        yield Msg('checkpoint') # allows us to pause the run 
        yield from bps.one_shot(detectors_list) #triggers and reads everything in the detectors list
        yield Msg('sleep', None, delay)

    
    yield from bps.close_run()
    return uid

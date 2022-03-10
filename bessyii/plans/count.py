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

from bluesky.plans import scan_nd
from bluesky import utils
from bluesky.utils import Msg

from bluesky import preprocessors as bpp
from bluesky import plan_stubs as bps

def create_command_string_for_count(detectors, num, delay):
    """
    Create a string to attach to the metadata with the command used
    to start the scan

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    *args :
        For one dimension, ``motor, start, stop``.
        In general:

        .. code-block:: python

            motor1, start1, stop1,
            motor2, start2, start2,
            ...,
            motorN, startN, stopN

        Motors can be any 'settable' object (motor, temp controller, etc.)
    num : integer
        number of points
    
    Returns
    ----------
    command: a string representing the scan command

    Tested for
    --------
    :func:`bluesky.plans.scan`
    """
    try:
        # detectors
        detector_names = [det.name for det in detectors]
        detector_names_string = '['
        for d in detector_names:
            detector_names_string += d + ','
        detector_names_string = detector_names_string[0:-1] + ']'

        if delay == None:
            command = 'count('+detector_names_string+', '+str(num)+')'
        else:
            command = 'count('+detector_names_string+', '+str(num)+', delay='+str(delay)+')'
    except:
        command = 'It was not possible to create this entry'
    return command

class BessyCount:
    def __init__(self, st_det=None):
        self.st_det = st_det
        
    def count(self, detectors, num=1, delay=None, *, per_shot=None, md=None):
        """
        Take one or more readings from detectors.
        Parameters
        ----------
        detectors : list
            list of 'readable' objects
        num : integer, optional
            number of readings to take; default is 1
            If None, capture data until canceled
        delay : iterable or scalar, optional
            Time delay in seconds between successive readings; default is 0.
        per_shot : callable, optional
            hook for customizing action of inner loop (messages per step)
            Expected signature ::
            def f(detectors: Iterable[OphydObj]) -> Generator[Msg]:
                ...
        md : dict, optional
            metadata
        Notes
        -----
        If ``delay`` is an iterable, it must have at least ``num - 1`` entries or
        the plan will raise a ``ValueError`` during iteration.
        """
        if self.st_det != None:
            for st_detector in self.st_det:
                detectors.append(st_detector)
        
        if num is None:
            num_intervals = None
        else:
            num_intervals = num - 1
        
        command_elog = create_command_string_for_count(detectors, num, delay)
        
        _md = {'detectors': [det.name for det in detectors],
            'num_points': num,
            'num_intervals': num_intervals,
            'plan_args': {'detectors': list(map(repr, detectors)), 'num': num},
            'plan_name': 'count',
            'command_elog' : command_elog,
            'hints': {}
            }
        _md.update(md or {})
        _md['hints'].setdefault('dimensions', [(('time',), 'primary')])

        if per_shot is None:
            per_shot = bps.one_shot

        @bpp.stage_decorator(detectors)
        @bpp.run_decorator(md=_md)
        def inner_count():
            return (yield from bps.repeat(partial(per_shot, detectors),
                                        num=num, delay=delay))

        return (yield from inner_count())



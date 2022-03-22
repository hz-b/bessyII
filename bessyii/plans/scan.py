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

def create_command_string_for_scan(detectors, motor_names, args, num):
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
        # detrmining the scan type checking at num
        if isinstance(num, int):
            scan_type = 'scan'
        else:
            scan_type = 'scan_stepsize'
        # detectors
        detector_names = [det.name for det in detectors]
        detector_names_string = '['
        for d in detector_names:
            detector_names_string += d + ','
        detector_names_string = detector_names_string[0:-1] + ']'

        #motors, motor positions and number of points
        n_motors = int(len(args)/3)
        motors_string = ', '
        for n in range(n_motors):
            motors_string += motor_names[n] +', '+str(args[1+n*3])+', '+str(args[2+n*3])+', '
        motors_string += str(num)
        command = scan_type+'('+detector_names_string+motors_string+')'
    except:
        command = 'It was not possible to create this entry'
    return command

def scan(detectors, *args, num=None, per_step=None, md=None):
    """
    Scan over one multi-motor trajectory. with start and stop metadata

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
    per_step : callable, optional
        hook for customizing action of inner loop (messages per step).
        See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
        for details.
    md : dict, optional
        metadata

    See Also
    --------
    :func:`bluesky.plans.relative_inner_product_scan`
    :func:`bluesky.plans.grid_scan`
    :func:`bluesky.plans.scan_nd`
    """
    # For back-compat reasons, we accept 'num' as the last positional argument:
    # scan(detectors, motor, -1, 1, 3)
    # or by keyword:
    # scan(detectors, motor, -1, 1, num=3)
    # ... which requires some special processing.
    if num is None:
        if len(args) % 3 != 1:
            raise ValueError("The number of points to scan must be provided "
                             "as the last positional argument or as keyword "
                             "argument 'num'.")
        num = args[-1]
        args = args[:-1]

    if not (float(num).is_integer() and num > 0.0):
        raise ValueError(f"The parameter `num` is expected to be a number of "
                         f"steps (not step size!) It must therefore be a "
                         f"whole number. The given value was {num}.")
    num = int(num)

    md_args = list(chain(*((repr(motor), start, stop)
                           for motor, start, stop in partition(3, args))))
    motor_names = tuple(motor.name for motor, start, stop
                        in partition(3, args))
    md = md or {}
    
    command_elog = create_command_string_for_scan(detectors, motor_names, args, num)
    
    _md = {'plan_args': {'detectors': list(map(repr, detectors)),
                         'num': num, 'args': md_args,
                         'per_step': repr(per_step)},
           'plan_name': 'scan',
           'plan_pattern': 'inner_product',
           'plan_pattern_module': plan_patterns.__name__,
           'plan_pattern_args': dict(num=num, args=md_args),
           'motors': motor_names,
           'command_elog' : command_elog
           }
    _md.update(md)

    # get hints for best effort callback
    motors = [motor for motor, start, stop in partition(3, args)]

    # Give a hint that the motors all lie along the same axis
    # [(['motor1', 'motor2', ...], 'primary'), ] is 1D (this case)
    # [ ('motor1', 'primary'), ('motor2', 'primary'), ... ] is 2D for example
    # call x_fields because these are meant to be the x (independent) axis
    x_fields = []
    for motor in motors:
        x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

    default_dimensions = [(x_fields, 'primary')]

    default_hints = {}
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    # now add default_hints and override any hints from the original md (if
    # exists)
    _md['hints'] = default_hints
    _md['hints'].update(md.get('hints', {}) or {})

    full_cycler = plan_patterns.inner_product(num=num, args=args)

    return (yield from scan_nd(detectors, full_cycler,
                               per_step=per_step, md=_md))



def scan_intervals(detectors, *args, num=None, per_step=None, md=None):
    """
    Scan over one multi-motor trajectory. with start and stop metadata. 
    num is the number of intervals and not of points!!!

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
        number of intervals
    per_step : callable, optional
        hook for customizing action of inner loop (messages per step).
        See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
        for details.
    md : dict, optional
        metadata

    See Also
    --------
    :func:`bluesky.plans.relative_inner_product_scan`
    :func:`bluesky.plans.grid_scan`
    :func:`bluesky.plans.scan_nd`
    """
    # For back-compat reasons, we accept 'num' as the last positional argument:
    # scan(detectors, motor, -1, 1, 3)
    # or by keyword:
    # scan(detectors, motor, -1, 1, num=3)
    # ... which requires some special processing.
    if num is None:
        if len(args) % 3 != 1:
            raise ValueError("The number of intervals to scan must be provided "
                             "as the last positional argument or as keyword "
                             "argument 'num'.")
        num = args[-1]
        args = args[:-1]

    if not (float(num).is_integer() and num > 0.0):
        raise ValueError(f"The parameter `num` is expected to be a number of "
                         f"intervals (not step size!) It must therefore be a "
                         f"whole number. The given value was {num}.")
    num = int(num+1)

    md_args = list(chain(*((repr(motor), start, stop)
                           for motor, start, stop in partition(3, args))))
    motor_names = tuple(motor.name for motor, start, stop
                        in partition(3, args))
    md = md or {}
    
    command_elog = create_command_string_for_scan(detectors, motor_names, args, num-1)
    
    _md = {'plan_args': {'detectors': list(map(repr, detectors)),
                         'num': num, 'args': md_args,
                         'per_step': repr(per_step)},
           'plan_name': 'scan',
           'plan_pattern': 'inner_product',
           'plan_pattern_module': plan_patterns.__name__,
           'plan_pattern_args': dict(num=num, args=md_args),
           'motors': motor_names,
           'command_elog' : command_elog
           }
    _md.update(md)

    # get hints for best effort callback
    motors = [motor for motor, start, stop in partition(3, args)]

    # Give a hint that the motors all lie along the same axis
    # [(['motor1', 'motor2', ...], 'primary'), ] is 1D (this case)
    # [ ('motor1', 'primary'), ('motor2', 'primary'), ... ] is 2D for example
    # call x_fields because these are meant to be the x (independent) axis
    x_fields = []
    for motor in motors:
        x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

    default_dimensions = [(x_fields, 'primary')]

    default_hints = {}
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    # now add default_hints and override any hints from the original md (if
    # exists)
    _md['hints'] = default_hints
    _md['hints'].update(md.get('hints', {}) or {})

    full_cycler = plan_patterns.inner_product(num=num, args=args)

    return (yield from scan_nd(detectors, full_cycler,
                               per_step=per_step, md=_md))



def scan_stepsize(detectors, *args, step=None, per_step=None, md=None):
    """
    Scan over one multi-motor trajectory. with start and stop metadata

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
    step : float
        step size for all the motors
    per_step : callable, optional
        hook for customizing action of inner loop (messages per step).
        See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
        for details.
    md : dict, optional
        metadata

    See Also
    --------
    :func:`bluesky.plans.relative_inner_product_scan`
    :func:`bluesky.plans.grid_scan`
    :func:`bluesky.plans.scan_nd`
    """
    # For back-compat reasons, we accept 'step' as the last positional argument:
    # scan(detectors, motor, -1, 1, 3)
    # or by keyword:
    # scan(detectors, motor, -1, 1, step=3)
    # ... which requires some special processing.
    if step is None:
        if len(args) % 3 != 1:
            raise ValueError("The step size to scan must be provided "
                             "as the last positional argument or as keyword "
                             "argument 'step'.")
        step = args[-1]
        args = args[:-1]

    num = int((args[2]-args[1])/step+1)

    md_args = list(chain(*((repr(motor), start, stop)
                           for motor, start, stop in partition(3, args))))
    motor_names = tuple(motor.name for motor, start, stop
                        in partition(3, args))
    md = md or {}
    
    command_elog = create_command_string_for_scan(detectors, motor_names, args, step)
    
    _md = {'plan_args': {'detectors': list(map(repr, detectors)),
                         'num': step, 'args': md_args,
                         'per_step': repr(per_step)},
           'plan_name': 'scan',
           'plan_pattern': 'inner_product',
           'plan_pattern_module': plan_patterns.__name__,
           'plan_pattern_args': dict(step=step, args=md_args),
           'motors': motor_names,
           'command_elog' : command_elog
           }
    _md.update(md)

    # get hints for best effort callback
    motors = [motor for motor, start, stop in partition(3, args)]

    # Give a hint that the motors all lie along the same axis
    # [(['motor1', 'motor2', ...], 'primary'), ] is 1D (this case)
    # [ ('motor1', 'primary'), ('motor2', 'primary'), ... ] is 2D for example
    # call x_fields because these are meant to be the x (independent) axis
    x_fields = []
    for motor in motors:
        x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

    default_dimensions = [(x_fields, 'primary')]

    default_hints = {}
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    # now add default_hints and override any hints from the original md (if
    # exists)
    _md['hints'] = default_hints
    _md['hints'].update(md.get('hints', {}) or {})

    full_cycler = plan_patterns.inner_product(num=num, args=args)

    return (yield from scan_nd(detectors, full_cycler,
                               per_step=per_step, md=_md))


def rel_scan_intervals(detectors, *args, num=None, per_step=None, md=None):
    """
    Scan over one multi-motor trajectory relative to current position.
    num is the number of intervals and not of points!!!
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
            motorN, startN, stopN,
        Motors can be any 'settable' object (motor, temp controller, etc.)
    num : integer
        number of points
    per_step : callable, optional
        hook for customizing action of inner loop (messages per step).
        See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
        for details.
    md : dict, optional
        metadata
    See Also
    --------
    :func:`bluesky.plans.rel_grid_scan`
    :func:`bluesky.plans.inner_product_scan`
    :func:`bluesky.plans.scan_nd`
    """
    _md = {'plan_name': 'rel_scan'}
    md = md or {}
    _md.update(md)
    motors = [motor for motor, start, stop in partition(3, args)]

    @bpp.reset_positions_decorator(motors)
    @bpp.relative_set_decorator(motors)
    def inner_rel_scan():
        return (yield from scan_intervals(detectors, *args, num=num,
                                per_step=per_step, md=_md))

    return (yield from inner_rel_scan())

class BessyScans:
    def __init__(self, st_det=None):
        self.st_det = st_det
        
    def scan(self, detectors, *args, num=None, per_step=None, md=None):
        """
        Scan over one multi-motor trajectory. with start and stop metadata

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
        per_step : callable, optional
            hook for customizing action of inner loop (messages per step).
            See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
            for details.
        md : dict, optional
            metadata

        See Also
        --------
        :func:`bluesky.plans.relative_inner_product_scan`
        :func:`bluesky.plans.grid_scan`
        :func:`bluesky.plans.scan_nd`
        """
        # For back-compat reasons, we accept 'num' as the last positional argument:
        # scan(detectors, motor, -1, 1, 3)
        # or by keyword:
        # scan(detectors, motor, -1, 1, num=3)
        # ... which requires some special processing.
        if self.st_det != None:
            for st_detector in self.st_det:
                detectors.append(st_detector)
        if num is None:
            if len(args) % 3 != 1:
                raise ValueError("The number of points to scan must be provided "
                                "as the last positional argument or as keyword "
                                "argument 'num'.")
            num = args[-1]
            args = args[:-1]

        if not (float(num).is_integer() and num > 0.0):
            raise ValueError(f"The parameter `num` is expected to be a number of "
                            f"steps (not step size!) It must therefore be a "
                            f"whole number. The given value was {num}.")
        num = int(num)

        md_args = list(chain(*((repr(motor), start, stop)
                            for motor, start, stop in partition(3, args))))
        motor_names = tuple(motor.name for motor, start, stop
                            in partition(3, args))
        md = md or {}
        
        command_elog = create_command_string_for_scan(detectors, motor_names, args, num)
        
        _md = {'plan_args': {'detectors': list(map(repr, detectors)),
                            'num': num, 'args': md_args,
                            'per_step': repr(per_step)},
            'plan_name': 'scan',
            'plan_pattern': 'inner_product',
            'plan_pattern_module': plan_patterns.__name__,
            'plan_pattern_args': dict(num=num, args=md_args),
            'motors': motor_names,
            'command_elog' : command_elog
            }
        _md.update(md)

        # get hints for best effort callback
        motors = [motor for motor, start, stop in partition(3, args)]

        # Give a hint that the motors all lie along the same axis
        # [(['motor1', 'motor2', ...], 'primary'), ] is 1D (this case)
        # [ ('motor1', 'primary'), ('motor2', 'primary'), ... ] is 2D for example
        # call x_fields because these are meant to be the x (independent) axis
        x_fields = []
        for motor in motors:
            x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

        default_dimensions = [(x_fields, 'primary')]

        default_hints = {}
        if len(x_fields) > 0:
            default_hints.update(dimensions=default_dimensions)

        # now add default_hints and override any hints from the original md (if
        # exists)
        _md['hints'] = default_hints
        _md['hints'].update(md.get('hints', {}) or {})

        full_cycler = plan_patterns.inner_product(num=num, args=args)

        return (yield from scan_nd(detectors, full_cycler,
                                per_step=per_step, md=_md))

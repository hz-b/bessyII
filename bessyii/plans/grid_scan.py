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


def create_command_string_for_grid_scan(detectors, motor_names, args):
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

        #motors, motor positions and number of points
        n_motors = int(len(args)/4)
        motors_string = ''
        for n in range(n_motors):
            motors_string += ', '+motor_names[n] +', '+str(args[1+n*4])+', '+str(args[2+n*4])+', '+str(args[3+n*4])
        command = 'grid_scan('+detector_names_string+motors_string+')'
    except:
        command = 'It was not possible to create this entry'
    return command

class BessyGridScan:
    def __init__(self, st_det=None):
        self.st_det = st_det
        
    def grid_scan(self, detectors, *args, snake_axes=None, per_step=None, md=None):
        """
        Scan over a mesh; each motor is on an independent trajectory.
        Parameters
        ----------
        detectors: list
            list of 'readable' objects
        ``*args``
            patterned like (``motor1, start1, stop1, num1,``
                            ``motor2, start2, stop2, num2,``
                            ``motor3, start3, stop3, num3,`` ...
                            ``motorN, startN, stopN, numN``)
            The first motor is the "slowest", the outer loop. For all motors
            except the first motor, there is a "snake" argument: a boolean
            indicating whether to following snake-like, winding trajectory or a
            simple left-to-right trajectory.
        snake_axes: boolean or iterable, optional
            which axes should be snaked, either ``False`` (do not snake any axes),
            ``True`` (snake all axes) or a list of axes to snake. "Snaking" an axis
            is defined as following snake-like, winding trajectory instead of a
            simple left-to-right trajectory. The elements of the list are motors
            that are listed in `args`. The list must not contain the slowest
            (first) motor, since it can't be snaked.
        per_step: callable, optional
            hook for customizing action of inner loop (messages per step).
            See docstring of :func:`bluesky.plan_stubs.one_nd_step` (the default)
            for details.
        md: dict, optional
            metadata
        See Also
        --------
        :func:`bluesky.plans.rel_grid_scan`
        :func:`bluesky.plans.inner_product_scan`
        :func:`bluesky.plans.scan_nd`
        """
        # Notes: (not to be included in the documentation)
        #   The deprecated function call with no 'snake_axes' argument and 'args'
        #         patterned like (``motor1, start1, stop1, num1,``
        #                         ``motor2, start2, stop2, num2, snake2,``
        #                         ``motor3, start3, stop3, num3, snake3,`` ...
        #                         ``motorN, startN, stopN, numN, snakeN``)
        #         The first motor is the "slowest", the outer loop. For all motors
        #         except the first motor, there is a "snake" argument: a boolean
        #         indicating whether to following snake-like, winding trajectory or a
        #         simple left-to-right trajectory.
        #   Ideally, deprecated and new argument lists should not be mixed.
        #   The function will still accept `args` in the old format even if `snake_axes` is
        #   supplied, but if `snake_axes` is not `None` (the default value), it overrides
        #   any values of `snakeX` in `args`.

        if self.st_det != None:
            for st_detector in self.st_det:
                detectors.append(st_detector)
        
        args_pattern = plan_patterns.classify_outer_product_args_pattern(args)
        if (snake_axes is not None) and \
                (args_pattern == plan_patterns.OuterProductArgsPattern.PATTERN_2):
            raise ValueError("Mixing of deprecated and new API interface is not allowed: "
                            "the parameter 'snake_axes' can not be used if snaking is "
                            "set as part of 'args'")

        # For consistency, set 'snake_axes' to False if new API call is detected
        if (snake_axes is None) and \
                (args_pattern != plan_patterns.OuterProductArgsPattern.PATTERN_2):
            snake_axes = False

        chunk_args = list(plan_patterns.chunk_outer_product_args(args, args_pattern))
        # 'chunk_args' is a list of tuples of the form: (motor, start, stop, num, snake)
        # If the function is called using deprecated pattern for arguments, then
        # 'snake' may be set True for some motors, otherwise the 'snake' is always False.

        # The list of controlled motors
        motors = [_[0] for _ in chunk_args]

        # Check that the same motor is not listed multiple times. This indicates an error in the script.
        if len(set(motors)) != len(motors):
            raise ValueError(f"Some motors are listed multiple times in the argument list 'args': "
                            f"'{motors}'")

        if snake_axes is not None:

            def _set_snaking(chunk, value):
                """Returns the tuple `chunk` with modified 'snake' value"""
                _motor, _start, _stop, _num, _snake = chunk
                return _motor, _start, _stop, _num, value

            if isinstance(snake_axes, collections.abc.Iterable) and not isinstance(snake_axes, str):
                # Always convert to a tuple (in case a `snake_axes` is an iterator).
                snake_axes = tuple(snake_axes)

                # Check if the list of axes (motors) contains repeated entries.
                if len(set(snake_axes)) != len(snake_axes):
                    raise ValueError(f"The list of axes 'snake_axes' contains repeated elements: "
                                    f"'{snake_axes}'")

                # Check if the snaking is enabled for the slowest motor.
                if len(motors) and (motors[0] in snake_axes):
                    raise ValueError(f"The list of axes 'snake_axes' contains the slowest motor: "
                                    f"'{snake_axes}'")

                # Check that all motors in the chunk_args are controlled in the scan.
                #   It is very likely that the script running the plan has a bug.
                if any([_ not in motors for _ in snake_axes]):
                    raise ValueError(f"The list of axes 'snake_axes' contains motors "
                                    f"that are not controlled during the scan: "
                                    f"'{snake_axes}'")

                # Enable snaking for the selected axes.
                #   If the argument `snake_axes` is specified (not None), then
                #   any `snakeX` values that could be specified in `args` are ignored.
                for n, chunk in enumerate(chunk_args):
                    if n > 0:  # The slowest motor is never snaked
                        motor = chunk[0]
                        if motor in snake_axes:
                            chunk_args[n] = _set_snaking(chunk, True)
                        else:
                            chunk_args[n] = _set_snaking(chunk, False)

            elif snake_axes is True:  # 'snake_axes' has boolean value `True`
                # Set all 'snake' values except for the slowest motor
                chunk_args = [_set_snaking(_, True) if n > 0 else _
                            for n, _ in enumerate(chunk_args)]
            elif snake_axes is False:  # 'snake_axes' has boolean value `True`
                # Set all 'snake' values
                chunk_args = [_set_snaking(_, False) for _ in chunk_args]
            else:
                raise ValueError(f"Parameter 'snake_axes' is not iterable, boolean or None: "
                                f"'{snake_axes}', type: {type(snake_axes)}")

        # Prepare the argument list for the `outer_product` function
        args_modified = []
        for n, chunk in enumerate(chunk_args):
            if n == 0:
                args_modified.extend(chunk[:-1])
            else:
                args_modified.extend(chunk)
        full_cycler = plan_patterns.outer_product(args=args_modified)

        md_args = []
        motor_names = []
        motors = []
        for i, (motor, start, stop, num, snake) in enumerate(chunk_args):
            md_args.extend([repr(motor), start, stop, num])
            if i > 0:
                # snake argument only shows up after the first motor
                md_args.append(snake)
            motor_names.append(motor.name)
            motors.append(motor)
        command_elog = create_command_string_for_grid_scan(detectors, motor_names, args) 
        _md = {'shape': tuple(num for motor, start, stop, num, snake
                            in chunk_args),
            'extents': tuple([start, stop] for motor, start, stop, num, snake
                                in chunk_args),
            'snaking': tuple(snake for motor, start, stop, num, snake
                                in chunk_args),
            # 'num_points': inserted by scan_nd
            'plan_args': {'detectors': list(map(repr, detectors)),
                            'args': md_args,
                            'per_step': repr(per_step)},
            'plan_name': 'grid_scan',
            'plan_pattern': 'outer_product',
            'plan_pattern_args': dict(args=md_args),
            'plan_pattern_module': plan_patterns.__name__,
            'motors': tuple(motor_names),
            'command_elog' : command_elog,
            'hints': {},
            }
        _md.update(md or {})
        _md['hints'].setdefault('gridding', 'rectilinear')
        try:
            _md['hints'].setdefault('dimensions', [(m.hints['fields'], 'primary')
                                                for m in motors])
        except (AttributeError, KeyError):
            ...

        return (yield from scan_nd(detectors, full_cycler,
                                per_step=per_step, md=_md))




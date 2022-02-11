import numpy as np
import datetime
from bluesky.plans import list_scan
from bluesky.plans import plan_patterns

def create_command_string_for_exafs_scan(detectors, motor_name, regions,  args):
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

        scan_type = 'exafs_scan'
 
        # detectors
        detector_names = [det.name for det in detectors]
        detector_names_string = '['
        for d in detector_names:
            detector_names_string += d + ','
        detector_names_string = detector_names_string[0:-1] + ']'

        #motors, motor positions and number of points

        motors_string = ', '
        motors_string += motor_name +', regions='+str(regions)
        for n in range(regions):
            motors_string += ', '+str(args[0+n*3])+','+str(args[1+n*3])+','+str(args[2+n*3])

        command = scan_type+'('+detector_names_string+motors_string+')'
    except:
        command = 'It was not possible to create this entry'
    return command

def exafs_scan(detectors,motor,regions=1, *args, per_step=None, md=None,scan=True):
    """
    scan a motor over multiple regions, read from a number of detectors
    
    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    motor: positioner 
        Motors can be any 'settable' object (motor, temp controller, etc.)
    regions: integer
        The number of regions to be specfied
    *args :
        for one region
        
        start, stop, step_size
        
        for N regions
        
        start0, stop0, step_size0, start1,stop1, step_size1, .... startN, stopN, step_sizeN
        
    per_step : callable, optional
        hook for customizing action of inner loop (messages per step)
        Expected signature:
        ``f(detectors, motor, step) -> plan (a generator)``
    md : dict, optional
        metadata

    See Also
    --------
    :func:`bluesky.plans.list_scan
    """
    
    if len(args)%regions !=0:  
        raise ValueError("Each region requires three arguments: start,stop,step_size"
                         "You defined ",regions, "region(s) and", str(len(args)), "argument(s)")
    
    md = md or {}  # reset md if it is None.
    
    
    for n in range(regions):
        print("Region ", n+1,': start=',args[0+n*3],', stop=', args[1+n*3], 'step_size=', args[2+n*3] )
        if n==0:
            points = np.arange(args[0+n*3],args[1+n*3]+args[2+n*3],args[2+n*3])
    
        elif n-1 != regions:
            points_temp = np.arange(args[0+n*3]+args[2+n*3],args[1+n*3]+args[2+n*3],args[2+n*3])
            points=np.concatenate((points,points_temp))
           
    print("The total number of points for your scan is:", points.shape[0])
    print("The estimated time, counting 6 seconds per point is (h:m:s):", str(datetime.timedelta(seconds=(points.shape[0]*6))))
    print('\nYou defined the following motor positions for the scan (not all of them will be printed on screen):')
    print(points)
    
    
    command_elog = create_command_string_for_exafs_scan(detectors, motor.name, regions, args) 
    _md = {'detectors': [det.name for det in detectors],
           'motors': motor.name,
           'num_points': points.shape[0],
           'num_intervals': points.shape[0] - 1,
           'plan_args': {'detectors': list(map(repr, detectors)),
                         'motors': motor.name,
                         'args': list(args),
                         'per_step': repr(per_step)},
           'plan_name': 'exafs_scan',
           'plan_pattern': 'inner_list_product',
           'plan_pattern_module': plan_patterns.__name__,
           'plan_pattern_args': list([repr(motor)])+list(points),
           'hints': {},
           'command_elog' : command_elog
           }
    _md.update(md or {})
    
    if scan == False:
        return
    
    yield from list_scan(detectors, motor, points, per_step=per_step, md=_md)

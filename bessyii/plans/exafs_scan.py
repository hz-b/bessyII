import numpy as np
import datetime
from bluesky.plans import list_scan
from bluesky.plans import plan_patterns

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
           'hints': {}
           }
    _md.update(md or {})
    
    if scan == False:
        return
    
    yield from list_scan(detectors, motor, points, per_step=per_step, md=_md)

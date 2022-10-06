from bluesky.run_engine import RunEngine
from ophyd import Kind,Device 

class RunEngineBessy(RunEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._silent_det = []
    
    def __call__(self, *args, **metadata_kw):
        kind_map = {} # dictionary with original hinted/normal states. 
        #make sure the plan has detectors. if not we don't need silent detectors
        if 'detectors' in args[0].gi_frame.f_locals:
            # NOTE: we use detector instance is the key - to avoid problem with hacked component names (e.g. keithley sets readback name to the device name)
            for det in self._silent_det:
                if not det in args[0].gi_frame.f_locals['detectors'] and det not in args[0].gi_frame.f_locals['args']:
                    # handle Device(s) explicitly - for all components marked as hinted set then to normal
                    if isinstance(det, Device):
                        hinted_components = [cc for cc in det.component_names if getattr(det, cc).kind == Kind.hinted]
                        kind_map[det]=hinted_components
                        for cc in hinted_components:
                            getattr(det, cc).kind = Kind.normal
                    # duck typing for other types - if it has field called "kind" than change it to "Kind.normal"
                    elif hasattr(det,"kind"):
                        kind_map[det] = det.kind
                        det.kind = Kind.normal
                
            args[0].gi_frame.f_locals['detectors'] += self._silent_det
        try: # wrap it in try-finally - we want to restore original state even if there was an error in executing run engine
            super().__call__(*args, **metadata_kw)
        finally:
            for det in kind_map:
                # restoring all marked/modified detectors
                if isinstance(det, Device):
                    for cc in  kind_map[det]:
                        getattr(det, cc).kind = Kind.hinted # we explicitly selected hinted components before, so we it set now back to hinted.
                # duck typing for other types - if it has field called "kind" than change it to whatever it was
                elif hasattr(det,"kind"): 
                    det.kind = kind_map[det]
                else:
                    raise AssertionError("Unknown kind of detector in the saved list - this should never happen!")  
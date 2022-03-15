from bluesky.run_engine import RunEngine
from ophyd import Kind        

class RunEngineBessy(RunEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._silent_det = []
    
    def __call__(self, *args, **metadata_kw):
        kind_map = {}
        for det in self._silent_det:
            if not det in args[0].gi_frame.f_locals['detectors']:
                kind_map[det.name] = det.val.kind
                det.val.kind = Kind.normal
            
        args[0].gi_frame.f_locals['detectors'] += self._silent_det
        try:
            super().__call__(*args, **metadata_kw)
        finally:
            for det in self._silent_det:
                if det.name in kind_map.keys():
                    det.val.kind = kind_map[det.name]


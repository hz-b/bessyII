from bluesky.run_engine import RunEngine

class RunEngineBessy(RunEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._standard_det = None
    
    def add_standard_detectors(self, st_det_list):
        self._standard_det = st_det_list
    
    def __call__(self, *args, **metadata_kw):
        if self._standard_det != None:
            for det in self._standard_det:
                args[0].gi_frame.f_locals['detectors'] += det
        super().__call__(*args, **metadata_kw)
        

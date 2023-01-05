from bluesky.run_engine import RunEngine
from ophyd import Kind,Device 
import inspect

class RunEngineBessy(RunEngine):
    """RunEngine modifications at BESYYII


    """    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def __call__(self, *args, **metadata_kw):
        kind_map = {} # dictionary with original hinted/normal states. 

        metadata_kw.setdefault('commad',inspect.stack()[1].code_context)


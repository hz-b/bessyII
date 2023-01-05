from bluesky.run_engine import RunEngine
import inspect

class RunEngineBessy(RunEngine):
    """RunEngine modifications at BESYYII


    """    
    
    def __call__(self, *args, **metadata_kw):

        metadata_kw.setdefault('command',inspect.stack()[1].code_context)
        super().__call__(*args, **metadata_kw)

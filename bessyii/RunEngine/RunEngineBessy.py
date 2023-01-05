from bluesky.run_engine import RunEngine

class RunEngineBessy(RunEngine):
    """RunEngine modifications at BESYYII


    """    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def __call__(self, *args, **metadata_kw):

        metadata_kw.setdefault('commad',inspect.stack()[1].code_context)

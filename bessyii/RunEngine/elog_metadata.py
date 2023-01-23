from . import RunEngineCallPreprocessor
import inspect

class eLogCallWrapper(RunEngineCallPreprocessor):
    """
    Inject calling command into the metadata
    """
    def before(self, runengine, args, metadata_kw)->None:
        metadata_kw.setdefault('command_elog',inspect.stack()[2].code_context)
        pass

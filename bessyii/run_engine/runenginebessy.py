from bluesky.run_engine import RunEngine

class RunEngineCallPreprocessor:
    """
    Base class for the run engine call preprocessor

    it does not do much but ensures that all needed methods are defined

    """
    def __init__(self,*args,**kwargs) -> None:
        pass
    
    def before(self, runengine:RunEngine, args, metadata_kw)->None:
        """
        before() method called before main call of the run engine
        """
        pass

    def after(self)->None:
        """
        after() method called after main call of the run engine
        """
        pass


class RunEngineBessy(RunEngine):
    """RunEngine modifications at BESSYII

    List of modifications:
    - call pre/post processors.
        Call preprocessors allow to modify call arguments (e.g. inject additional metadata) for the run engine.
        See elog_metadata.py and detectors.py for an example
    """    

    def register_call_preprocessor(self, call_prerocessor:RunEngineCallPreprocessor):
        """ register a call preprocessor

        Call preprocessors must be derived from RunEngineCallPreprocessor class. 

        Args:
            call_prerocessor (RunEngineCallPreprocessor): instance of a call preprocessor to be added

        Raises:
            TypeError: in case suplied object does not have RunEngineCallPreprocessor as one of its parents
        """
        if not isinstance(call_prerocessor,RunEngineCallPreprocessor):
            raise TypeError("call_prerocessor must be derived from RunEngineCallPreprocessor")
        self._call_preprocessors.append(call_prerocessor)

    def remove_call_preprocessor(self, call_prerocessor:RunEngineCallPreprocessor):
        """ Removes previously registered call preprocessor from the list.

        Repeated removes or removing preprocessor which was not added previously is not an error

        Args:
            call_prerocessor (RunEngineCallPreprocessor): preprocessor to be removed
        """
        if call_prerocessor in self._call_preprocessors:
            self._call_preprocessors.remove(call_prerocessor)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._call_preprocessors = []
    
    def __call__(self, *args, **metadata_kw):
        cb:RunEngineCallPreprocessor
        for cb in self._call_preprocessors:
            cb.before(self, args, metadata_kw)
        try: # wrap it in try-finally - we want to restore original state even if there was an error in executing run engine
            super().__call__(*args, **metadata_kw)
        finally:
            for cb in reversed(self._call_preprocessors):
                cb.after()
            
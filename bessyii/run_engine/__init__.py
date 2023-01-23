from .runenginebessy import RunEngineBessy,RunEngineCallPreprocessor

from .detectors import DetectorKindFixCallWrapper
from .elog_metadata import eLogCallWrapper

def register_default_call_preprocessors(RE):
    """
    Helper to register default/standrd call preprocessors
    """
    RE.register_call_preprocessor(eLogCallWrapper())
    #RE.register_call_preprocessor(DetectorKindFixCallWrapper())

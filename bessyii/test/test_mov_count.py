import pytest
from bessyii.plans.flying import mov_count

from ophyd.sim import motor,det, noisy_det

from databroker.v2 import temp



from bluesky.callbacks.best_effort import BestEffortCallback
from event_model import RunRouter
from bluesky import RunEngine

RE = RunEngine({})
db = temp()
RE.subscribe(db.v1.insert)


def factory(name, doc):
    # Documents from each run is routed to an independent
    #   instance of BestEffortCallback
    bec = BestEffortCallback()
    return [bec], []

rr = RunRouter([factory])
RE.subscribe(rr)


from bluesky.preprocessors import SupplementalData
sd = SupplementalData()
RE.preprocessors.append(sd)

from ophyd.sim import noisy_det
sd.baseline = [noisy_det]


def test_mov_count():

    motor.delay = 1
   
    RE(mov_count([det],motor,1,2,0.1))
    


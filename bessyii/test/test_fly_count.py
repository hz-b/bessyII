import pytest
from bessyii.plans.flying import flycount, flyscan

from bessyii_devices.flyer import MyMotor, MyDetector, BasicFlyer
#Flyer Sim
my_det = MyDetector('EMILEL:TestIOC00:', name='my_det')
fdev = MyMotor('EMILEL:TestIOC00:', name='fdev')
fdev.wait_for_connection()

# Example: nested runs
from ophyd.sim import det, flyer1, flyer2  # simulated hardware
from databroker.v2 import temp


from bluesky.plans import count
from bluesky.callbacks.best_effort import BestEffortCallback
import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from databroker import Broker
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


def test_flycount():
    fdev.start_pos.put(1)
    fdev.end_pos.put(1.1)
    fdev.velocity.put(0.2)
    RE(flycount([my_det],fdev))
    
def test_flyscan():
    
    RE(flyscan([my_det],fdev,2.2,2.4,0.2))
    

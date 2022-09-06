

import pytest
from bessyii.default_detectors import BessySupplementalData, init_silent, close_silent

from bessyii_devices.ring import Ring

from ophyd.sim import motor, noisy_det, det, det1, det2, det3, motor1, motor2
from bluesky.preprocessors import SupplementalData
from bluesky import RunEngine 
from databroker.v2 import temp
from bluesky.callbacks.best_effort import BestEffortCallback
#from bluesky.preprocessors import pchain
from bluesky.utils import Msg


## Set up env
RE = RunEngine({})
db = temp()
RE.subscribe(db.v1.insert)

#create status signal

from ophyd import Signal

light_status = Signal(name="light_status")

test_string = "Test"
light_status.put(test_string)

#initiate SupplementalData
sd = BessySupplementalData(baseline=[det1], silent_devices=[det1, det2],light_status=light_status, beamline_name = 'HARD')

#add the functions to the RunEngine library so you can call them via Msg
RE.register_command('init_silent', init_silent)
RE.register_command('close_silent', close_silent)

RE.preprocessors.append(sd)

bessy2 = Ring('MDIZ3T5G:', name='ring')
bessy2.wait_for_connection()

from bluesky.plans import scan, count
from bluesky.plan_stubs import mv

 

def test_msg_len():
    
    D = BessySupplementalData(light_status=light_status, beamline_name = 'HARD')
    original = list(count([det1]))
    processed = list(D(count([det1])))
    # should add 0 
    assert len(processed) ==  len(original)
    
def test_meta():

    RE(count([det1]))
    run = db[-1]
    start_doc = run.metadata['start']
    assert start_doc['beamline_status'] == "HARD_"+str(test_string)


    
    
 


import pytest
from bessyii.default_detectors import SupplementalDataSilentDets, init_silent, close_silent

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

#initiate SupplementalData
sd = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det1, det2])

#add the functions to the RunEngine library so you can call them via Msg
RE.register_command('init_silent', init_silent)
RE.register_command('close_silent', close_silent)

RE.preprocessors.append(sd)
bec = BestEffortCallback()
RE.subscribe(bec)


bessy2 = Ring('MDIZ3T5G:', name='ring')
bessy2.wait_for_connection()

from bluesky.plans import scan, count
from bluesky.plan_stubs import mv

 

def double_plan_count(detectors, num=1, delay=None):
    
    yield from count(detectors, num=num, delay=delay)
    yield from count(detectors, num=num, delay=delay)

def test_baseline_single_det():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1])
    original = list(count([det1]))
    processed = list(D(count([det1])))
    # should add 2X (trigger, wait, create, read, save)
    assert len(processed) == 10 + len(original)
    
    
def test_baseline_double_det():
    # two baseline detectors
    D = SupplementalDataSilentDets(baseline=[det1])
    original = list(count([det1]))
    D.baseline.append(det2)
    processed = list(D(count([det2])))
    # should add 2X (trigger, triger, wait, create, read, read, save)
    assert len(processed) == 14 + len(original)

def test_baseline_det_consective_runs():
    # two baseline detectors applied to a plan with two consecutive runs
    D = SupplementalDataSilentDets(baseline=[det1])
    original = list(list(count([det1])) + list(count([det1])))
    processed = list(D(double_plan_count([det1])))
    # should add 4X (trigger, wait, create, read, save)

    assert len(processed) == 20 + len(original)
    
def test_baseline_det_no_plan_det():
    # test a plan without detectors like a mv
    D = SupplementalDataSilentDets(baseline=[det1])
    original = list(mv(motor1, 1))

    processed = list(D(mv(motor1, 1)))
    # should add nothing

    assert len(processed) == len(original)

#Repeat the tests but with the silent dets added


def test_baseline_single_det_single_silent_det():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det2])
    original = list(count([det3]))
    processed = list(D(count([det3])))
    # should add 2X (trigger, wait, create, read, save) + (stage, init_silent,  trigger, read, ,close_silent, unstage)
    assert len(processed) == 16 + len(original)
    
    
def test_baseline_single_det_single_silent_det_in_dets():
    # one baseline detector, one silent device, but it's included in list of detectors
    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det2])
    original = list(count([det2]))
    processed = list(D(count([det2])))
    # should add 2X (trigger, wait, create, read, save)
    assert len(processed) == 10 + len(original)
    
def test_baseline_double_det_single_silent_det():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1,det], silent_devices=[det2])
    original = list(count([det3]))
    processed = list(D(count([det3])))
    # should add 2X (trigger,trigger,  wait, create,read, read, save) + (stage, init_silent,  trigger, read, ,close_silent, unstage)
    assert len(processed) == 20 + len(original)
    
def test_baseline_det_consective_runs_single_silent():
    # two baseline detectors applied to a plan with two consecutive runs
    D = SupplementalDataSilentDets(baseline=[det1],silent_devices=[det2])
    original = list(list(count([det1])) + list(count([det1])))
    processed = list(D(double_plan_count([det1])))
    # should add 4X (trigger, wait, create, read, save) + 2X(stage, init_silent,  trigger, read, close_silent, unstage)

    assert len(processed) == 32 + len(original)
    
from bluesky.callbacks import CallbackBase
from bluesky.callbacks.best_effort import hinted_fields

class SiletDevicesTestCallback(CallbackBase):


    def __init__(self):
        self._descriptors = {}
        self.hinted_list = []
        self.dev_list = []
            
    def descriptor(self, doc):
        self._descriptors[doc['uid']] = doc
        self.dev_list = list(doc['data_keys'].keys())
        self.hinted_list = hinted_fields(doc)
        

    def clear(self):

        self._descriptors.clear()
        

sd_test = SiletDevicesTestCallback()   

from ophyd import Kind

def test_baseline_single_det_single_silent_det_hinted_check():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det2])
    original = list(count([det3]))
    processed = list(D(count([det3])))
    # should add 2X (trigger, wait, create, read, save) + (stage, init_silent,  trigger, read, ,close_silent, unstage)
    assert len(processed) == 16 + len(original)
    
    RE(D(count([det3])),sd_test)
    
    #confirm that we would only plot det3, but that both det3 and det2 would be recorded in the databroker
    assert set(sd_test.hinted_list) == set(['det3'])
    assert set(sd_test.dev_list) == set(['det3','det2'])
    
    #confirm that the detector is put back to hinted
    assert det2.val.kind == Kind.hinted
    
    
def test_baseline_single_det_double_silent_det_w_ring_hinted_check():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det2,bessy2])

    
    RE(D(count([det3])),sd_test)
    
    #confirm that we would only plot det3, but that both det3 and det2 would be recorded in the databroker
    assert set(sd_test.hinted_list) == set(['det3'])
    assert set(sd_test.dev_list) == set(['det3','det2', 'ring_current', 'ring_lifetime'])
    
    #confirm that the detector is put back to hinted
    assert bessy2.current.kind == Kind.hinted
    assert bessy2.lifetime.kind == Kind.hinted
    
def test_baseline_single_det_double_silent_motor_hinted_check():
    # one baseline detector
    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[motor1])

    
    RE(D(count([det3])),sd_test)
    
    #confirm that we would only plot det3, but that both det3 and det2 would be recorded in the databroker
    assert set(sd_test.hinted_list) == set(['det3'])
    assert set(sd_test.dev_list) == set(['det3','motor1_setpoint','motor1'])
    
    #confirm that the detector is put back to hinted
    assert motor1.setpoint.kind == Kind.normal
    assert motor1.readback.kind == Kind.hinted

def test_baseline_single_det_multiple_same_silent():

    D = SupplementalDataSilentDets(baseline=[det1], silent_devices=[det1, det2, det2])

    RE(D(count([det3])), sd_test)

    assert det2.val.kind == Kind.hinted


    
    
    
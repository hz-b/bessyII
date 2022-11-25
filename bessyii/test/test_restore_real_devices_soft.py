import pytest
from bessyii.restore import restore, RestoreHelpers
from bessyii.default_detectors import BessySupplementalData, init_silent, close_silent
from bessyii.RunEngine.RunEngineBessy import RunEngineBessy as RunEngine
from bluesky.plan_stubs import mv
#from bluesky import RunEngine
from databroker.v2 import temp
import numpy as np
import time

#create the status pv's
from ophyd import Signal
light_status = Signal(name="light_status")
test_string = "Test"
light_status.put(test_string)

## Set up env
RE = RunEngine({})
db = temp()
RE.subscribe(db.v1.insert)

beamline_name = "Test Beamline"
RE.md["beamline"] = beamline_name

##set up some test devices
from bessyii_devices.au import AU4, AU13
from bessyii_devices.m3_m4_mirrors import SMU2, SMU3, Hexapod
from bessyii_devices.sim import SimPositionerDone
from bessyii_devices.diodes import DiodeEMIL
from bessyii_devices.undulator import HelicalUndulator
from bessyii_devices.pgm import PGMSoft





sim_shutter = SimPositionerDone(name='sim_shutter')
ue48_au4_sissy = AU4('AU04Y02U112L:', name= "ue48_au4_sissy")
ue48_au4_sissy.wait_for_connection()

ue48_m4_sissy = SMU2 ('HEX6OS12L:' ,name='ue48_m4_sissy')
ue48_m4_sissy.wait_for_connection()

ue48_sissy_diode_2 = DiodeEMIL("DIODE02Y02U112L:M0",name = "ue48_sissy_diode_2" )
ue48_sissy_diode_2.wait_for_connection()

ue48 = HelicalUndulator("UE48IT6R:", name = "ue48")
ue48.wait_for_connection()

ue48_au1 = AU13("WAUY01U012L:", name = "ue48_au1")
ue48_au1.wait_for_connection()

ue48_pgm = PGMSoft("ue481pgm1:", name="ue48_pgm")
ue48_pgm.wait_for_connection()

#Create the baseline
from bessyii.default_detectors import BessySupplementalData

# instantiate the helper with status and shutters
restore_helpers = RestoreHelpers(db,beamline_name = beamline_name, shutter = sim_shutter )

def switch(end_station,devices, uid=None,md=None):
        yield from restore_helpers.switch_beamline(end_station,devices, uid=uid,md=md)
        
# Create a baseline
sd = BessySupplementalData()
sd.baseline = [ue48,ue48_au1,ue48_pgm,ue48_au4_sissy,ue48_m4_sissy,ue48_sissy_diode_2]

# Add the beamline status PV
sd.light_status = light_status

RE.preprocessors.append(sd)

#Perform a plan to add something to the databroker
from bluesky.plans import count
from ophyd.sim import noisy_det, motor
RE(count([noisy_det]))
#get the uid
uid = db[-1].metadata['start']['uid'][:8]


## define the tests
@pytest.mark.skip(reason="this works")
def test_restore_diodes_and_filters():
    
    #test whether we can restore the configuration of a parent device (and all it's children)

    #read the initial configuration of the device 

    init_conf = ue48_sissy_diode_2.read_configuration()
    init_pos = ue48_sissy_diode_2.user_setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48_sissy_diode_2,26))

    ue48_sissy_diode_2.velocity.set(3)


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_sissy_diode_2] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_sissy_diode_2.read_configuration()

    assert ue48_sissy_diode_2.user_setpoint.get() == init_pos

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]


@pytest.mark.skip(reason="this works")
def test_restore_au4():
    
    #test whether we can restore the configuration of a parent device (and all it's children)

    #read the initial configuration of the device 

    init_conf = ue48_au4_sissy.read_configuration()
    init_pos = ue48_au4_sissy.top.user_setpoint.get()
    #Move the motors to some other positions

    RE(mv(ue48_au4_sissy.top,15))

    ue48_au4_sissy.top.velocity.set(3)
    ue48_au4_sissy.bottom.velocity.set(3)
    ue48_au4_sissy.left.velocity.set(3)
    ue48_au4_sissy.right.velocity.set(3)

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_au4_sissy,ue48_au4_sissy.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_au4_sissy.read_configuration()

    assert ue48_au4_sissy.top.user_setpoint.get() == init_pos

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]

@pytest.mark.skip(reason="this works")
def test_restore_m4_choice():
    
    #test whether we can restore the position of m4_smu_choice

    #read the initial configuration of the device 

    init_conf = ue48_m4_sissy.choice.read_configuration()
    init_pos = ue48_m4_sissy.rtx.setpoint.get()
    init_pos_readback = ue48_m4_sissy.tx.readback.get()
    init_choice = ue48_m4_sissy.choice.readback.get()
   
    #Move the motors to some other positions
    RE(mv(ue48_m4_sissy.tx,ue48_m4_sissy.rtx.setpoint.get()+5))

    #Now switch the light to the other end station
    if ue48_m4_sissy.choice.readback.get() == "SISSY-I":
         
        RE(mv(ue48_m4_sissy.choice,"SISSY-II"))
    
    else: 
        RE(mv(ue48_m4_sissy.choice,"SISSY-I"))
    

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_m4_sissy.choice] 

    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_m4_sissy.choice.read_configuration()

    ## Check that the setpoint has been correctly set
    assert ue48_m4_sissy.rtx.setpoint.get() == init_pos 

    ##check that the readback is within 3um
    assert np.abs(ue48_m4_sissy.tx.readback.get() - init_pos_readback) < 3

    ##Check that the choice parameter is correctly set
    assert ue48_m4_sissy.choice.readback.get() == init_choice


    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]


@pytest.mark.skip(reason="this works")
def test_restore_undulator():
    


    #read the initial configuration of the device 

    init_conf = ue48.read_configuration()
    init_pos_gap = ue48.gap.setpoint.get()
    init_pos_shift = ue48.shift.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48.gap,101, ue48.shift,0.1))

    


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48, ue48.gap, ue48.shift] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48.read_configuration()

    assert ue48.gap.setpoint.get() == init_pos_gap
    assert ue48.shift.setpoint.get() == init_pos_shift

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]   
    


@pytest.mark.skip(reason="no write access on this machine (sissy-serv-03)")
def test_restore_au13():
    
    #read the initial configuration of the device 

    init_conf = ue48_au1.read_configuration()
    init_pos = ue48_au1.top.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48_au1.top,-0.5))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_au1, ue48_au1.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_au1.read_configuration()

    assert ue48_au1.top.setpoint.get() == init_pos
   

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"] 

#@pytest.mark.skip(reason="this works")
def test_restore_pgm():
    
    #read the initial configuration of the device 

    init_conf = ue48_pgm.read_configuration()
    init_au4 = ue48_au4_sissy.top.user_setpoint.get()
    init_pos_en = ue48_pgm.en.setpoint.get()
    init_pos_grating = ue48_pgm.grating_translation.setpoint.get() #note we are looking at the absolute value!
    init_pos_slit = ue48_pgm.slit.setpoint.get()

    #Move the motors to some other positions
    ue48_pgm.ID_on.set(0) #id off
    
    ue48_pgm.grating_translation.move(41).wait()
    ue48_pgm.cff.set(2.3) #set the cff
    ue48_pgm.en.move(init_pos_en+1).wait()

    if ue48_pgm.slit.branch.get() == "CAT":

        ue48_pgm.slit.branch.set("STXM")
    
    else:

        ue48_pgm.slit.branch.set("CAT")

    init_pos_slit = ue48_pgm.slit.setpoint.get()

    ue48_pgm.slit.move(init_pos_slit+1).wait()

    ue48_au4_sissy.top.move(12).wait()
    


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_pgm,ue48_au4_sissy.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the new conf
    new_conf = ue48_pgm.read_configuration()

    #Check that all the positions have been restored
    assert ue48_pgm.en.setpoint.get() == init_pos_en 
    assert ue48_pgm.grating_translation.setpoint.get() == init_pos_grating
    assert ue48_pgm.slit.setpoint.get() == init_pos_slit
    assert ue48_au4_sissy.top.user_setpoint.get() == init_au4
    #Check that all the positions have been restored
    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]  

    #finally check that the order that things were set is correct
    
    en_time = ue48_pgm.en.setpoint.read()[ue48_pgm.en.setpoint.name]['timestamp']
    grating_time = ue48_pgm.grating_translation.setpoint.read()[ue48_pgm.grating_translation.setpoint.name]['timestamp']
    slit_time = ue48_pgm.slit.setpoint.read()[ue48_pgm.slit.setpoint.name]['timestamp']
    
    #Check that the grating is set first, then the slit, then the energy
    assert grating_time < slit_time < en_time 
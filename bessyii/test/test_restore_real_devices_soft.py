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
from bessyii_devices.au import AU4, AU13, AU2
from bessyii_devices.pinhole import Pinhole
from bessyii_devices.m3_m4_mirrors import SMU2, SMU3, Hexapod
from bessyii_devices.sim import SimPositionerDone
from bessyii_devices.diodes import DiodeEMIL
from bessyii_devices.undulator import HelicalUndulator
from bessyii_devices.pgm import PGMSoft


sim_shutter = SimPositionerDone(name='sim_shutter')
ue48_au4_sissy = AU4('AU04Y02U112L:', name= "ue48_au4_sissy")
ue48_au4_sissy.wait_for_connection()

ue48_m4_sissy = SMU2 ('HEX6OS12L:' ,name='ue48_m4_sissy')
ue48_m3_cat   = Hexapod('HEX4OS12L:' ,name='ue48_m3_cat'  )
#ue48_m4_sissy.wait_for_connection(timeout=20)

ue48_sissy_diode_2 = DiodeEMIL("DIODE02Y02U112L:M0",name = "ue48_sissy_diode_2" )
ue48_sissy_diode_2.wait_for_connection()

ue48 = HelicalUndulator("UE48IT6R:", name = "ue48")
ue48.wait_for_connection()

ue48_au1 = AU13("WAUY01U012L:", name = "ue48_au1")
ue48_au2       = AU2 ('ue481pgm1:',   name='ue48_au2'      )
ue48_au3_sissy = AU13('AUY02U112L:',  name='ue48_au3_sissy')
ue48_au3_cat   = AU13('AUY02U212L:',  name='ue48_au3_cat'  )
ue48_au4_cat   = AU4 ('AU04Y02U212L:',   name='ue48_au4_cat'      )
ue48_au4_sissy = AU4 ('AU04Y02U112L:',   name='ue48_au4_sissy'      )


# Pinhole
ph =   Pinhole('PHY01U012L:', name='ph')

#ue48_au1.wait_for_connection()

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
sd.baseline = [ue48,ue48_au1,ue48_pgm,ue48_au4_sissy,ue48_m4_sissy,ue48_m3_cat, ue48_sissy_diode_2, ue48_au3_sissy, ue48_au3_cat, ue48_au2, ph]

# Add the beamline status PV
sd.light_status = light_status

RE.preprocessors.append(sd)

#Perform a plan to add something to the databroker
from bluesky.plans import count
from ophyd.sim import noisy_det, motor
RE(count([noisy_det]))
#get the uid
uid = db[-1].metadata['start']['uid'][:8]

def test_uid_exists():

    baseline = db[uid].baseline
## define the tests
@pytest.mark.skip(reason="this works")
def test_restore_diodes_and_filters():
    
    #test whether we can restore the configuration of a parent device (and all it's children)

    #read the initial configuration of the device 

    init_conf = ue48_sissy_diode_2.read_configuration()
    init_pos = ue48_sissy_diode_2.user_setpoint.get()

    #Move the motors to some other positions

    ue48_sissy_diode_2.move(25).wait()

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


#@pytest.mark.skip(reason="this works")
def test_restore_au4():
    
    #test whether we can restore the configuration of a parent device (and all it's children)

    #read the initial configuration of the device 

    init_conf = ue48_au4_sissy.read_configuration()
    init_pos_top = ue48_au4_sissy.top.user_setpoint.get()
    init_pos_bottom = ue48_au4_sissy.bottom.user_setpoint.get()
    #Move the motors to some other positions

    RE(mv(ue48_au4_sissy.top,15,ue48_au4_sissy.bottom,15))

    ue48_au4_sissy.top.velocity.set(3)
    ue48_au4_sissy.bottom.velocity.set(3)
    ue48_au4_sissy.left.velocity.set(3)
    ue48_au4_sissy.right.velocity.set(3)

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_au4_sissy,ue48_au4_sissy.top,ue48_au4_sissy.bottom] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_au4_sissy.read_configuration()

    assert ue48_au4_sissy.top.user_setpoint.get() == init_pos_top
    assert ue48_au4_sissy.bottom.user_setpoint.get() == init_pos_bottom

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]

@pytest.mark.skip(reason="this works")
def test_restore_m4_choice():
    
    #test whether we can restore the position of m4_smu_choice

    #read the initial configuration of the device 

    init_conf = ue48_m4_sissy.choice.read_configuration()
    init_pos = ue48_m4_sissy.tx.setpoint.get()
    init_pos_readback = ue48_m4_sissy.tx.readback.get()
    init_choice = ue48_m4_sissy.choice.readback.get()
   
    #Move the motors to some other positions
    RE(mv(ue48_m4_sissy.tx,ue48_m4_sissy.tx.setpoint.get()+5))

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
    assert ue48_m4_sissy.tx.setpoint.get() == init_pos 

    ##check that the readback is within 3um
    assert np.abs(ue48_m4_sissy.tx.readback.get() - init_pos_readback) < 3

    ##Check that the choice parameter is correctly set
    assert ue48_m4_sissy.choice.readback.get() == init_choice


    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]

@pytest.mark.skip(reason="this works")
def test_restore_m4_hexapod(): 
    
    #test whether we can restore the position of m4 hexapod which should have the same interface as the other hexapods

    #read the initial configuration of the device 

    init_conf = ue48_m4_sissy.read_configuration()
    init_pos = ue48_m4_sissy.tx.setpoint.get()
    init_pos_readback = ue48_m4_sissy.tx.readback.get()
    init_choice = ue48_m4_sissy.choice.readback.get()
   
    #Move the motors to some other positions
    RE(mv(ue48_m4_sissy.tx,ue48_m4_sissy.tx.setpoint.get()+5))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_m4_sissy] 

    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_m4_sissy.read_configuration()

    ## Check that the setpoint has been correctly set
    assert ue48_m4_sissy.tx.setpoint.get() == init_pos 

    ##check that the readback is within 3um
    assert np.abs(ue48_m4_sissy.tx.readback.get() - init_pos_readback) < 3

    ##Check that the choice parameter is correctly set
    assert ue48_m4_sissy.choice.readback.get() == init_choice


    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]

@pytest.mark.skip(reason="this works")
def test_restore_m3_hexapod(): 
    
    #read the initial configuration of the device 

    init_conf = ue48_m3_cat.read_configuration()
    init_pos_readback = ue48_m3_cat.real_position
   
   
    #Move the motors to some other positions

    RE(mv(ue48_m3_cat.tx,ue48_m3_cat.tx.setpoint.get()+5))
    RE(mv(ue48_m3_cat.ty,ue48_m3_cat.ty.setpoint.get()+5))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_m3_cat] 

    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_m3_cat.read_configuration()


    ##check that the readback is within 3um
    assert abs(ue48_m3_cat.real_position - init_pos_readback) < 10

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"]

@pytest.mark.skip(reason="this works")
def test_restore_undulator():

    #read the initial configuration of the device 
    init_conf = ue48.read_configuration()
    init_pos_gap = ue48.gap.setpoint.get()
    init_pos_shift = ue48.shift.setpoint.get()

    #Move the motors to some other positions


    ue48.id_control.set(0) #give control to undulator so we can set the gap and shift
    RE(mv(ue48.gap,101, ue48.shift,0.1))
    ue48.id_control.set(1) #set it back to test

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
def test_restore_au1():
    
    #read the initial configuration of the device 

    init_conf = ue48_au1.read_configuration()
    init_pos = ue48_au1.top.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48_au1.top,-4))

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

@pytest.mark.skip(reason="this works")
def test_restore_au3():
    
    #read the initial configuration of the device 

    init_conf = ue48_au3_sissy.read_configuration()
    init_pos = ue48_au3_sissy.top.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48_au3_sissy.top,-4))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_au3_sissy, ue48_au3_sissy.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_au3_sissy.read_configuration()

    assert abs(ue48_au3_sissy.top.setpoint.get() - init_pos) < 0.2
   

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"] 

@pytest.mark.skip(reason="this works")
def test_restore_au2():
    
    #read the initial configuration of the device 

    init_conf = ue48_au2.read_configuration()
    init_pos = ue48_au2.top.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ue48_au2.top,1))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ue48_au2, ue48_au2.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ue48_au2.read_configuration()

    assert abs(ue48_au2.top.setpoint.get() - init_pos) < 0.2
   

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"] 

@pytest.mark.skip(reason="no write access on sissy-serv-03")
def test_restore_ph():
    
    #read the initial configuration of the device 

    init_conf = ph.read_configuration()
    init_pos = ph.h.setpoint.get()

    #Move the motors to some other positions

    RE(mv(ph.h,-0.2))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [ph,ph.h] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the current conf
    new_conf = ph.read_configuration()

    assert abs(ph.h.setpoint.get() - init_pos) < 0.1
   

    for key, item in new_conf.items():

        assert new_conf[key]["value"] == init_conf[key]["value"] 

@pytest.mark.skip(reason="this works")
def test_restore_pgm():
    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline

    #read the initial configuration of the device 

    init_conf = ue48_pgm.read_configuration()
    init_au4 = ue48_au4_sissy.top.user_setpoint.get()
    init_pos_en = ue48_pgm.en.setpoint.get()
    init_pos_grating = ue48_pgm.grating_translation.readback.get() #note we are looking at the absolute value!

    #Move the motors to some other positions
    ue48_pgm.ID_on.set(0) #id off
    
    ue48_pgm.grating_translation.move(43).wait()
    ue48_pgm.cff.set(2.3) #set the cff
    ue48_pgm.en.move(init_pos_en+1).wait()
    init_pos_slit = ue48_pgm.slit.readback.get()
    ue48_pgm.slit.move(init_pos_slit+1).wait()

    if ue48_pgm.slit.branch.get() == "CAT":

        ue48_pgm.slit.branch.set("STXM")
    
    else:

        ue48_pgm.slit.branch.set("CAT")

    ue48_au4_sissy.top.move(12).wait()
    
    device_list = [ue48_pgm,ue48_pgm.grating_trans_sel,ue48_pgm.slit, ue48_pgm.en,ue48_au4_sissy.top] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #read the new conf
    new_conf = ue48_pgm.read_configuration()

    #Check that all the positions have been restored
    assert ue48_pgm.en.setpoint.get() == init_pos_en 
    assert abs(ue48_pgm.grating_translation.readback.get() - init_pos_grating) <= 0.1
    assert abs(ue48_pgm.slit.readback.get()- init_pos_slit) <= 0.1
    assert ue48_au4_sissy.top.user_setpoint.get() == init_au4
    #Check that all the positions have been restored
    for key, item in new_conf.items():

        if "stxm" not in key:
            assert new_conf[key]["value"] == init_conf[key]["value"]  

    #finally check that the order that things were set is correct
    
    en_time = ue48_pgm.en.setpoint.read()[ue48_pgm.en.setpoint.name]['timestamp']
    grating_time = ue48_pgm.grating_translation.setpoint.read()[ue48_pgm.grating_translation.setpoint.name]['timestamp']
    slit_time = ue48_pgm.slit.setpoint.read()[ue48_pgm.slit.setpoint.name]['timestamp']
    
    #Check that the grating is set first, then the slit, then the energy
    assert grating_time < slit_time < en_time 


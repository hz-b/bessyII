import pytest
from bessyii.restore import restore, RestoreHelpers
from bessyii.default_detectors import BessySupplementalData, init_silent, close_silent
from bessyii.RunEngine.RunEngineBessy import RunEngineBessy as RunEngine

#from bluesky import RunEngine
from databroker.v2 import temp


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
from bessyii_devices.sim import SimPositionerDone,SimSMUHexapod, sim_smu, sim_hex, sim_mono, sim_motor, p3, stage,m1,m2,m3
from ophyd.sim import noisy_det,det, motor

sim_shutter = SimPositionerDone(name='sim_shutter')
m4_smu = SimSMUHexapod(name='m4_smu')

# instantiate the helper with status and shutters

restore_helpers = RestoreHelpers(db,beamline_name = beamline_name, shutter = sim_shutter )

def switch(end_station,devices, uid=None,md=None):
        yield from restore_helpers.switch_beamline(end_station,devices, uid=uid,md=md)
        

# Create a baseline
sd = BessySupplementalData()

sd.baseline = [m1, m2, stage,p3,m4_smu,sim_mono]

# Add the beamline status PV
sd.light_status = light_status

RE.preprocessors.append(sd)

# Move the motors to some positions

from bluesky.plan_stubs import mv

config = [1,2,3,4,5,6]
m1.velocity.set(config[0])
m2.velocity.set(config[1])
stage.a.x.velocity.set(config[2])
stage.b.y.velocity.set(config[3])
stage.a.config_param.set(config[4])
stage.config_param.set(config[5])


positions = [1.3, 2.1, 2.3, 1.2]
RE(mv(m1,positions[0], m2, positions[1], stage.a.x, positions[2], stage.b.y, positions[3]))

#record the initial config for later test


m1_initial_config_values = {}
for k, v in m1.read_configuration().items():
    m1_initial_config_values[k]=v['value']


stage_initial_config_values = {}
for k, v in stage.read_configuration().items():
    stage_initial_config_values[k]=v['value']

stage_a_initial_config_values = {}
for k, v in stage.a.read_configuration().items():
    stage_a_initial_config_values[k]=v['value']
    
stage_a_x_initial_config_values = {}
for k, v in stage.a.x.read_configuration().items():
    stage_a_x_initial_config_values[k]=v['value']

#Move the sim mono somewhere:
sim_mono_initial_values = [1,2,3,4]
sim_mono.a.x.move(sim_mono_initial_values[0])
sim_mono.a.y.move(sim_mono_initial_values[1])
sim_mono.b.x.move(sim_mono_initial_values[2])
sim_mono.b.y.move(sim_mono_initial_values[3])

#Perform a plan to add something to the databroker
from bluesky.plans import scan

RE(scan([noisy_det], motor, -1,1,2))

#get the uid
uid = db[-1].metadata['start']['uid'][:8]


   
## define the tests
def test_restore_configuration_parent():
    
    #test whether we can restore the configuration of a parent device (and all it's children)

    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [stage] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    
    stage_config_values = {}
    for k, v in stage.read_configuration().items():
        stage_config_values[k]=v['value']

    assert stage_config_values == stage_initial_config_values


    
## define the tests
def test_restore_configuration_child_with_parent_and_child():
    
    #test whether we can restore the configuration of a parent device (and all it's children), which sits in the middle of a device tree
    
    
    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [stage.a] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    
    stage_a_config_values = {}
    for k, v in stage.a.read_configuration().items():
        stage_a_config_values[k]=v['value']



    
    assert stage_a_config_values == stage_a_initial_config_values

## define the tests
def test_restore_configuration_child_with_parent_and_child_and_parent_in_list():
    
    #test whether we can restore the configuration of a parent device (and all it's children), which sits in the middle of a device tree
    
    
    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [stage.a,stage, stage.a.x] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    
    stage_a_config_values = {}
    for k, v in stage.a.read_configuration().items():
        stage_a_config_values[k]=v['value']

    stage_config_values = {}
    for k, v in stage.read_configuration().items():
        stage_config_values[k]=v['value']

    
    assert stage_a_config_values == stage_a_initial_config_values
    assert stage_config_values == stage_initial_config_values


    
def test_restore_configuration_child():
    
    #test whether we can restore the configuration of a child with parents and no children
    
    
    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [stage.a.x] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    
    stage_a_x_config_values = {}
    for k, v in stage.a.x.read_configuration().items():
        stage_a_x_config_values[k]=v['value']

    assert stage_a_x_config_values == stage_a_x_initial_config_values




    
def test_restore_configuration_device():
    
    #test whether we can restore the configuration of a single device without children
    
    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))


    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [m1] 
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    
    m1_config_values = {}
    for k, v in m1.read_configuration().items():
        m1_config_values[k]=v['value']

    
    assert m1_config_values == m1_initial_config_values
    
def test_restore_values():

    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [m1,m2,stage.a.x, stage.b.y]
    
    #attempt the restore
    RE(restore(baseline_stream, device_list))
    
    restored_val=[]
    for device in device_list :
        
        restored_val.append(device.readback.get())
    
    assert restored_val == positions
    
def test_ommit_restore_values():
    
    #test that we ONLY restore values of positioners in the list, and not children of devices which are positioners
    
    #Move the motors to some other positions
    new_config = [2,3,4,5,6,7]
    m1.velocity.set(new_config[0])
    m2.velocity.set(new_config[1])
    stage.a.x.velocity.set(new_config[2])
    stage.b.y.velocity.set(new_config[3])
    stage.a.config_param.set(new_config[4])
    stage.config_param.set(new_config[5])

    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [m1,m2,stage ]
    
    #attempt the restore
    RE(restore(baseline_stream, device_list))
    
    restored_val=[]
    for device in [m1,m2,stage.a.x, stage.b.y] :
        
        restored_val.append(device.readback.get())
    
    test_positions = positions[0:2] + new_positions[2:4]
    assert restored_val == test_positions   

def test_device_not_in_baseline_values():
    
    #test that we fail gracefully if we don't have the device in the baseline
    
    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [m3]
    
    #attempt the restore
    with pytest.raises(KeyError) as e_info:
        RE(restore(baseline_stream, device_list))
        
def test_pseudo_positioner():
    
    #move the pseudo_positioner to some initial position and config
    m4_smu.move(4,5,6,7,8,9)
    original_position = m4_smu.position
    m4_smu.choice.move(1)
    m4_smu.choice.config_dev_1.config_param_a.set(1)
    m4_smu.choice.config_dev_2.config_param_b.set(1)
    
    #Perform a measurement to generate some new baseline readings
    RE(scan([noisy_det],p3.pseudo1,4,5,10))
    
    #Now move it again to a new position
    m4_smu.move(8,7,6,5,4,3)
    new_position = m4_smu.position
    m4_smu.choice.move(0)
    m4_smu.choice.config_dev_1.config_param_a.set(2)
    m4_smu.choice.config_dev_2.config_param_b.set(2)

    baseline_stream = db[-1].baseline

    #Now check that we can restore the original positions of the choice
    RE(restore(baseline_stream,[m4_smu.choice]))

    assert m4_smu.position == new_position #check that the other positioners were not set
    assert m4_smu.choice.readback.get() == 1
    assert m4_smu.choice.config_dev_1.config_param_a.get() == 1
    assert m4_smu.choice.config_dev_2.config_param_b.get() == 1

    ##now restore the position
    m4_smu.choice.move(0)
    RE(restore(baseline_stream,[m4_smu]))

    assert m4_smu.choice.readback.get() == 0
    assert m4_smu.position == original_position

def test_search_restore():
    
    current_end_station = light_status.get()

    print(current_end_station)
    
    #create the device list 
    device_list = [m1,m2,stage.a.x, stage.b.y]
    
    #Record the initial values
    initial_val = []
    
    for device in device_list :
        
        initial_val.append(device.readback.get())
    
    #Move the motors to some other positions
    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))
    
    #change the readback of the endstation  
    new_end_station = "new_es"
    light_status.put(new_end_station)
    
    #create the device list 
    device_list = [m1,m2,stage.a.x, stage.b.y]

    #Perform a search trying to restore to the earlier positions
    restore_plan = switch(current_end_station, device_list)
    
    RE(restore_plan)
    
    restored_val = []
    
    for device in device_list :
        
        restored_val.append(device.readback.get())
    
    assert restored_val == initial_val
    
    ##Now check we can move back the other way
    
    #Perform a search trying to restore to the earlier positions
    
    
        
    restore_plan = switch(new_end_station, device_list)
    
    RE(restore_plan)
        
    restored_val = []
    
    for device in device_list :
        
        restored_val.append(device.readback.get())
    
    assert restored_val == new_positions
    
def test_close_shutter():
    
    
    current_end_station = light_status.get()
    
    #create the device list 
    device_list = [m1,m2,stage.a.x, stage.b.y]
    
    #Move the motors to some other positions
    new_positions = [0,0,0,0]
    RE(mv(m1,new_positions[0], m2, new_positions[1], stage.a.x, new_positions[2], stage.b.y, new_positions[3]))
    
    #change the readback of the endstation  
    new_end_station = "new_es"
    light_status.put(new_end_station)
    
    #open the shutter
    
    sim_shutter.set(1)
    
    #Perform a search trying to restore to the earlier positions
    restore_plan = switch(current_end_station, device_list)
    
    RE(restore_plan)
    
    assert sim_shutter.readback.get() == 0

def test_sim_pgm():


    #Run a plan to save the positions in the baseline
    new_positions = [4,12,2,124]
    RE(mv(sim_mono.a.x,new_positions[0], sim_mono.a.y, new_positions[1], sim_mono.b.x, new_positions[2], sim_mono.b.y, new_positions[3]))

    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [sim_mono] ## Note we are taking the top level device here which will also restore the sub components because we've defined it that way
    #attempt the restore
    RE(restore(baseline_stream, device_list))

    #find the values 
    restored_positions = [sim_mono.a.x.readback.get(),sim_mono.a.y.readback.get(),sim_mono.b.x.readback.get(),sim_mono.b.y.readback.get()]

    assert restored_positions == sim_mono_initial_values

    #Also check that the positioners were restored in the correct order
    a_x_timestamp = sim_mono.a.x.readback.read()[sim_mono.a.x.readback.name]['timestamp']
    a_y_timestamp = sim_mono.a.y.readback.read()[sim_mono.a.y.readback.name]['timestamp']
    b_x_timestamp = sim_mono.b.x.readback.read()[sim_mono.b.x.readback.name]['timestamp']
    b_y_timestamp = sim_mono.b.y.readback.read()[sim_mono.b.y.readback.name]['timestamp']

    #In this test device we will always restore a.x then a.y, then b.y then b.x
    assert a_x_timestamp < a_y_timestamp < b_y_timestamp < b_x_timestamp





    
    
    


    

import pytest
from bessyii.restore import restore
from ophyd.sim import motor, noisy_det
from ophyd import SoftPositioner, Signal, Device, Component as Cpt
from bluesky.preprocessors import SupplementalData
from bluesky import RunEngine
from databroker.v2 import temp
import numpy as np
## Set up env


RE = RunEngine({})
db = temp()
RE.subscribe(db.v1.insert)

##set up some test devices

from ophyd.sim import SynAxis
from bessyii_devices.positioners import PVPositionerDone

class SimPositionerDone(SynAxis, PVPositionerDone):
        
    def _setup_move(self, position):
        '''Move and do not wait until motion is complete (asynchronous)'''
        self.log.debug('%s.setpoint = %s', self.name, position)
        self.setpoint.put(position)
        if self.actuate is not None:
            self.log.debug('%s.actuate = %s', self.name, self.actuate_value)
            self.actuate.put(self.actuate_value)
        self._toggle_done()

m1 = SimPositionerDone(name='m1',readback_func=lambda x: x + np.random.rand() )
m2 = SimPositionerDone(name='m2',readback_func=lambda x: x + np.random.rand())
m3 = SimPositionerDone(name='m3',readback_func=lambda x: x + np.random.rand())

# make m2 have a readback.name different to m2.name
m2.readback.name = m2.name + '_readback'
from ophyd import EpicsMotor, Signal, Device, Component as Cpt
class Stage(Device):
    
    x = Cpt(SimPositionerDone)
    y = Cpt(SimPositionerDone)
    config_param = Cpt(Signal, kind='config')
    
class StageOfStage(Device):
    
    a = Cpt(Stage)
    b= Cpt(Stage)
    config_param = Cpt(Signal, kind='config')
    
stage = StageOfStage(name = 'stage')

# Create a baseline
sd = SupplementalData()

sd.baseline = [m1, m2, stage] 
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
positions_readbacks=[]
for device in [m1,m2,stage.a.x,stage.b.y] :

    positions_readbacks.append(device.readback.get())
    
def test_setpoints_not_equal_readbacks():
    
    assert positions != positions_readbacks
                       
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
    RE(restore(baseline_stream, device_list, use_readback=False))

    
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
    
def test_restore_values_setpoint():

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
    RE(restore(baseline_stream, device_list, use_readback=False))
    
    restored_val=[]
    for device in device_list :
        
        restored_val.append(device.setpoint.get())
    
    assert restored_val == positions
    
def test_restore_values_readback():

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
    RE(restore(baseline_stream, device_list, use_readback=True))
    
    restored_val=[]
    for device in device_list :
        
        restored_val.append(device.setpoint.get())
    
    assert restored_val == positions_readbacks
    
def test_ommit_restore_values_use_setpoint():
    
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
    RE(restore(baseline_stream, device_list, use_readback=False))
    
    restored_val=[]
    for device in [m1,m2,stage.a.x, stage.b.y] :
        
        restored_val.append(device.setpoint.get())
    
    test_positions = positions[0:2] + new_positions[2:4]
    assert restored_val == test_positions  
    
def test_ommit_restore_values_use_readback():
    
    #test that we ONLY restore values of positioners in the list, and not children of devices which are positioners, when we also use readback values to restore
    
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
    RE(restore(baseline_stream, device_list, use_readback=True))
    
    restored_val=[]
    for device in [m1,m2,stage.a.x, stage.b.y] :
        
        restored_val.append(device.setpoint.get())
    
    test_positions = positions_readbacks[0:2] + new_positions[2:4]
    assert restored_val == test_positions   

def test_device_not_in_baseline_values():
    
    #test that we fail gracefully if we don't have the device in the baseline
    
    #Now attempt to restore the original positions
    baseline_stream = db[uid].baseline
    
    device_list = [m3]
    
    #attempt the restore
    with pytest.raises(KeyError) as e_info:
        RE(restore(baseline_stream, device_list, use_readback=False))
        

    


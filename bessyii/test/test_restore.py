import pytest
from bessyii.restore import restore, RestoreHelpers
from ophyd.sim import motor, noisy_det
from ophyd import SoftPositioner, Signal, Device, Component as Cpt
from bessyii.default_detectors import BessySupplementalData, init_silent, close_silent
from bluesky import RunEngine
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
from ophyd.sim import SynAxis
from ophyd import Device, Component as Cpt
from bessyii_devices.positioners import PVPositionerDone
import time as ttime
import numpy as np



class ConfigDev(Device):

    config_param_a = Cpt(Signal, kind='config')
    config_param_b = Cpt(Signal, kind='config')
    config_param_c = Cpt(Signal, kind='config')

class SimPositionerDone(SynAxis, PVPositionerDone):

    """
    A PVPositioner which reports done immediately AND conforms to the standard of other positioners with signals for 
    
    setpoint
    readback
    done
    
    
    """

    config_dev_1 = Cpt(ConfigDev, kind='config')
    config_dev_2 = Cpt(ConfigDev, kind='config')

    def _setup_move(self, position):
        '''Move and do not wait until motion is complete (asynchronous)'''
        self.log.debug('%s.setpoint = %s', self.name, position)
        self.setpoint.put(position)
        if self.actuate is not None:
            self.log.debug('%s.actuate = %s', self.name, self.actuate_value)
            self.actuate.put(self.actuate_value)
        self._toggle_done()



        
    def __init__(self,
                 name,
                 readback_func=None,
                 value=0,
                 delay=0,
                 precision=3,
                 parent=None,
                 labels=None,
                 kind=None,**kwargs):
        super().__init__(name=name, parent=parent, labels=labels, kind=kind,readback_func=readback_func,delay=delay,precision=precision,
                         **kwargs)
        self.set(value)
    
    
    

m1 = SimPositionerDone(name='m1' )
m2 = SimPositionerDone(name='m2')
m3 = SimPositionerDone(name='m3')
sim_shutter = SimPositionerDone(name='sim_shutter')



# instantiate the helper with status and shutters

restore_helpers = RestoreHelpers(db,beamline_name = beamline_name, shutter = sim_shutter )

def switch(end_station,devices, uid=None,md=None):
        yield from restore_helpers.switch_beamline(end_station,devices, uid=uid,md=md)
        
        
        
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



#Create a PseudoPositioner

from ophyd.pseudopos import (
    PseudoPositioner,
    PseudoSingle,
    pseudo_position_argument,
    real_position_argument
)
from ophyd import Component, SoftPositioner


class Pseudo3x3(PseudoPositioner):
    """
    Interface to three positioners in a coordinate system that flips the sign.
    """
    pseudo1 = Component(PseudoSingle, limits=(-10, 10), egu='a')
    pseudo2 = Component(PseudoSingle, limits=(-10, 10), egu='b')
    pseudo3 = Component(PseudoSingle, limits=(-10, 10), egu='c')
    
    #add some offset to distinguish readback and setpoint
    real1 = Component(SimPositionerDone,value=0.1,readback_func=lambda x: 2*x)
    real2 = Component(SimPositionerDone,value=0.1,readback_func=lambda x: 2*x)
    real3 = Component(SimPositionerDone,value=0.1,readback_func=lambda x: 2*x)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        "Given a position in the psuedo coordinate system, transform to the real coordinate system."
        return self.RealPosition(
            real1=-pseudo_pos.pseudo1,
            real2=-pseudo_pos.pseudo2,
            real3=-pseudo_pos.pseudo3
        )

    @real_position_argument
    def inverse(self, real_pos):
        "Given a position in the real coordinate system, transform to the pseudo coordinate system."
        return self.PseudoPosition(
            pseudo1=-real_pos.real1,
            pseudo2=-real_pos.real2,
            pseudo3=-real_pos.real3
        )


class M4SMUSim(Pseudo3x3):

    _real = ["real1","real2","real3"]
    choice = Cpt(SimPositionerDone,kind='normal')

p3 = Pseudo3x3(name='p3')

m4_smu = M4SMUSim(name='m4_smu')



# Create a baseline
sd = BessySupplementalData()

sd.baseline = [m1, m2, stage,p3,m4_smu]

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
    
    #move the pseudo_positioner to some initial position
    m4_smu.move(4,5,6)
    m4_smu.choice.move(1)

    #with some initial config

    m4_smu.choice.config_dev_1.config_param_a.set(1)
    m4_smu.choice.config_dev_2.config_param_b.set(1)
    
    #Perform a measurement to generate some new baseline readings
    RE(scan([noisy_det],p3.pseudo1,4,5,10))
    
    #Now move it again to a new position
    m4_smu.move(6,7,8)
    m4_smu.choice.move(0)
    m4_smu.choice.config_dev_1.config_param_a.set(2)
    m4_smu.choice.config_dev_2.config_param_b.set(2)



    baseline_stream = db[-1].baseline
    
    print(baseline_stream.read())
    #Now check that we can restore the original positions
    RE(restore(baseline_stream,[m4_smu.choice]))
    
    assert m4_smu.choice.readback.get() == 1
    assert m4_smu.choice.config_dev_1.config_param_a.get() == 1
    assert m4_smu.choice.config_dev_2.config_param_b.get() == 1

    ##now restore the position
    RE(restore(baseline_stream,[m4_smu]))

    assert m4_smu.pseudo1.setpoint.get() == 4
    assert m4_smu.pseudo2.setpoint.get() == 5
    assert m4_smu.pseudo3.setpoint.get() == 6
    assert m4_smu.pseudo1.readback.get() == 8
    assert m4_smu.pseudo2.readback.get() == 10
    assert m4_smu.pseudo3.readback.get() == 12

def test_search_restore():
    
    current_end_station = light_status.get()
    
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
    
    
    


    

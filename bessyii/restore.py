from bluesky.plan_stubs import mv
from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)
from ophyd import PVPositioner, PositionerBase

import bluesky.preprocessors as bpp
from bluesky.protocols import Status

def restore(baseline_stream, devices, use_readback=True, md=None):
    """
    
    Restore the a set of devices to setpoint values defined in a baseline.
    The values taken at the start of the run are taken. 
    Configuration of the devices is also restored
    

    Parameters
    ----------
    baseline_stream : baseline stream 
        the baseline stream we want to restore from e.g db[-1].baseline
    devices : a list of devices
        the devices we are going to restore   
    use_readback : boolean
        if true (default) then restore readbacks, otherwise restore setpoints
    md : dict, optional
        metadata

   
    """
    
    _md = {'identifier': baseline_stream.metadata['start']['uid'],
           'plan_name': 'restore',
           'hints': {}
           }
    _md.update(md or {})
          
    
    baseline_data = baseline_stream.read()
    @bpp.run_decorator(md=_md)
    def inner_restore():
        status_objects = []
        
        #Restore Configuration
        for device in devices:
            
            #Check that this device does not have a parent in the list of devices
            if device.parent not in devices:
                
                #find the name of the device containing this device in the list
                
                if device.parent == None: # if this device is a top level parent then we can only configure it if it's in the baseline
                    
                    #get the configuration x_array from the baseline
                    configuration = baseline_stream.config[device.name].read()
                
                else:   # this is a child without parents in the list (but possibly parents in the baseline)
                    
                    list_of_parents_of_device = [device.parent]
                    current_parent = device.parent
                    while current_parent.parent != None:
                        current_parent = current_parent.parent
                        list_of_parents_of_device.append(current_parent)
                        
                    list_of_devices_in_baseline =[]
                    for k,v in baseline_stream.config.items():
                        list_of_devices_in_baseline.append(k)
                        
                    #find if there is a parent in the baseline
                    found_config = False
                    for parent_device in list_of_parents_of_device:
                        
                        if parent_device.name in list_of_devices_in_baseline:
                            
                            configuration = baseline_stream.config[parent_device.name].read()
                            found_config = True
                            break
                            
                    if not found_config:
                        
                        raise KeyError(f"There is no device in the baseline matching {device.name}")
                        

                #For each configuration attribute in our device, create a dict of the attribute name and the value we need to set it to
                configuration_dict = {}
                
                #create a list of signal names of the top level device
                name = (device.name+'.')
                signal_names = []
                for signal in device.get_instantiated_signals():

                    if signal[1].write_access:
                        signal_names.append(signal[0].replace(name,''))

                    
                for configuration_attr in device.configuration_attrs:
                    
                    #We only want to restore if the attribute is a signal
                    if configuration_attr in signal_names:
                        
                        
                        
                        configuration_dict[configuration_attr] = configuration[device.name +'_'+configuration_attr.replace('.','_')].values[0]
                

                #Perform the configuration for that device
                device.configure(configuration_dict)
            
            
                     
        #Restore the setpoint (we will work out readback later)
        for device in devices:
            
            #check that the device is a positioner
            if isinstance(device,PositionerBase):
                
                for attr in device.read_attrs:
                    if use_readback:
    
                        signal_name = device.readback.name
         
                    else:
                                                
                        signal_name = device.setpoint.name
                    
                    dev_obj = device
                    val = baseline_data[signal_name].values[0]
                    print(f"found {signal_name} in baseline, restoring to {val}")
                    ret = yield Msg('set', dev_obj, val, group = 'restore')
                    status_objects.append(ret)

        print(f"Restoring devices to run {baseline_stream.metadata['start']['uid']}")
        yield Msg('wait', None, group='restore')

        return tuple(status_objects)

    return(yield from inner_restore())

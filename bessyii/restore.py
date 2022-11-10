from bluesky.plan_stubs import mv, configure
from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)
from ophyd import PVPositioner, PositionerBase, PseudoPositioner

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

                    if hasattr(signal[1] ,'write_access'):
                        if signal[1].write_access:
                            signal_names.append(signal[0].replace(name,''))

                    
                for configuration_attr in device.configuration_attrs:
                    
                    #We only want to restore if the attribute is a signal
                    if configuration_attr in signal_names:
                        
                        
                        
                        configuration_dict[configuration_attr] = configuration[device.name +'_'+configuration_attr.replace('.','_')].values[0]
                

                #Perform the configuration for that device
                ret = yield from config(configuration_dict)
                status_objects.append(ret)
            
            
                     
        #Restore the setpoint (we will work out readback later)
        for device in devices:
            
            #check that the device is a positioner
            if isinstance(device,PositionerBase):
                
                # if it's a PseudoPositioner then write a position 
                if isinstance(device,PseudoPositioner):
                    
                    # create a position dictionary
                    position_dict = {}
                    
                    #calculate the values that the real positioners were set to
                    for real_axis in device.real_positioners:
                        
                        signal_name = real_axis.setpoint.name
                        signal_value = baseline_data[signal_name].values[0]
                        position_dict[real_axis._attr_name] = signal_value
                    
                    #From that real position derive the pseudo position we need to drive to
                    pseudo_pos = device.inverse(position_dict)
                    
                    #Use that position dictionary as the setpoint
                    dev_obj = device
                    setpoint_val = pseudo_pos
                    print(f"found {signal_name} in baseline, restoring to {position_dict}")
                    ret = yield Msg('set', dev_obj, setpoint_val, group = 'restore')
                    status_objects.append(ret)
                        
                #if it's not a PseudoPositioner then write the setpoint in the baseline again 
                else:
                    for attr in device.read_attrs:
                        if "setpoint" in str(attr):                         
                            signal_name = device.name + '_'+ attr
                          

                            dev_obj = device
                            setpoint_val = baseline_data[signal_name].values[0]
                            print(f"found {signal_name} in baseline, restoring to {setpoint_val}")
                            ret = yield Msg('set', dev_obj, setpoint_val, group = 'restore')
                            status_objects.append(ret)


        print(f"Restoring devices to run {baseline_stream.metadata['start']['uid']}")
        yield Msg('wait', None, group='restore')

        return tuple(status_objects)

    return(yield from inner_restore())


# Create a function specifically for switching beamlines. Put it in a class so we can import it from a package

from databroker.queries import TimeRange
from ophyd import EpicsSignalRO

from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)
import bluesky.plan_stubs as bps

class RestoreHelpers:
    """
    A class to help make the db variable global
    
    instantiate with 
    
      helpers = Helpers(db)


    """
    def __init__(self, db, shutter=None, beamline_name=None):
        self._db = db
        self._shutter = shutter
        self._beamline_name = beamline_name
        
     
       
        
    def switch_beamline(self,end_station,devices,gold=None,user=None,name=None, uid=None,md=None):

        """

        Restore the environment of the 

        Parameters
        ----------
        end_station: end_station we are going to move to
            SISSY1, SISSY2, CAT, STXM, PINK
        devices : a list of devices
            the devices we are going to restore
        gold: bool
            if asserted search the database for the last gold set at this end station
        user: string
            three letter HZB username added to metadata (like qqu)
        name: string
            The name of the snapshot if it was specified when taken. If there are more than one with the same name, the most recent one is used
        uid: identifier, optional
            The unique identifier to restore if we don't want the most recent
        md : dict, optional
            metadata

        """
        
        #Search the database for the most recent run performed that has this beamline name
        if uid == None and name == None:
            
            results = self._db

            
            if self._beamline_name:
           
                search_results = results.search({'beamline':self._beamline_name, "end_station": str(end_station) })
            
            else:
                
                search_results = results.search({"end_station": str(end_station) })
                
            if user != None:
                
                search_results = search_results.search({'username':user})
                
                if len(search_results) == 0:
                    raise ValueError(f'There are no runs with at beamline {self._beamline_name}, end_station {end_station}, taken by user {user}')
                
            if gold != None:
                
                search_results = search_results.search({'plan_name':'gold_snapshot'})
                
                if len(search_results) == 0:
                    raise ValueError(f'There are no gold runs with at beamline {self._beamline_name}, end_station {end_station}')
            
            
        
            if len(search_results) >0:
                run = search_results[-1]

            else:
                raise ValueError(f'There are no runs with at beamline {self._beamline_name}, end_station {end_station}')
        
        else:
            if name:
                
                search_results = self._db.search({'snapshot_name':name})
                
                if len(search_results) >0:
                    run = search_results[-1]
                
                if run.metadata['start']['end_station'] != end_station:

                    raise ValueError(f'The snapshot >{name}< was not taken at end_station {end_station}')
            
            else:
                
                run = self._db[uid]
            
                if run.metadata['start']['end_station'] != end_station:

                    raise ValueError(f'The uid {uid} was not taken at end_station {end_station}')
                
                      
        baseline = run.baseline
               
        
        #close the shutter
        if self._shutter != None:
            print(f"closing {self._shutter.name}")
            yield from bps.mv(self._shutter,0)
            
        
        
        #Restore the beamline to the settings described in this run        
        yield from restore(baseline, devices, md=md)
    

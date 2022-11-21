from bluesky.plan_stubs import mv, configure
from bluesky.utils import (
    separate_devices,
    all_safe_rewind,
    Msg,
    ensure_generator,
    short_uid as _short_uid,
)

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
        


        for device in devices:

            restore_dict = {}
            configuration = {}

            #find out if it's got parents
            #Check that this device does not have a parent in the list of devices
            if device.parent not in devices:
                found_config = False
                
                #find the name of the device containing this device in the list
                if device.parent == None: # if this device is a top level parent then we can only configure it if it's in the baseline
                    
                    #get the configuration x_array from the baseline
                    configuration = baseline_stream.config[device.name].read()
                    found_config = True
                
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
        

    
            # Make a dictionary that can be passed to device.restore
            
            for conf_attr in device.configuration_attrs:

                conf_attr_sig_name =device.name +"_"+conf_attr.replace(".","_")

            

                if conf_attr_sig_name in configuration:

                    restore_dict[conf_attr_sig_name] = configuration[conf_attr_sig_name].values[0]
            
            for key, data in baseline_data.items():

                if "setpoint" in key and device.name in key:
                    restore_dict[key] = data.values[0]

            #check if the device has a method restore()
            
            if hasattr(device, "restore"):

                if callable(device.restore):

                    #if it has a restore method then call it, pass the entire baseline dict. It is expected to search this and check what it needs to do

                    yield Msg('restore', device, restore_dict, group = 'restore')
            
            else:

                pass

    
        print(f"Restoring devices to run {baseline_stream.metadata['start']['uid']}")
        yield Msg('wait', None, group='restore')

        return tuple(status_objects)

    return(yield from inner_restore())


# Create a function specifically for switching beamlines. Put it in a class so we can import it from a package



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
        run = []
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
                
                      
               
        
        #close the shutter
        if self._shutter != None:
            print(f"closing {self._shutter.name}")
            yield from bps.mv(self._shutter,0)
            
        
        
        #Restore the beamline to the settings described in this run
        if run:        
            yield from restore(run.baseline, devices, md=md)
    

##### -------  Resource Lock -----------------

from bluesky.suspenders import SuspendWhenChanged
import os


def teardown_my_shell(RE,lock_list):
    
    """
    Thia function removes suspenders and unlocks the resources held by the locks in lock_list
    
    RE: Bluesky run engine 
    
    lock_list: list of lock objects
    
    """

    RE.clear_suspenders()
    ipython_session_id = os.getpid()
    
    if 'user_name' in RE.md:
    
        user_string = RE.md['user_name'] +" "+ str(ipython_session_id) +' ' + RE.md['hostname']
    else:
    
        user_string =  str(ipython_session_id) +' ' + RE.md['hostname']
    
    if lock_list != None:
        for lock in lock_list:
            if (lock.free.get() != 1) and (lock.user.get() == user_string):
                lock.unlock()
                print(f"Unlocking {lock.name}")




def lock_resource(RE,lock_list):
    
    """
    The function attaches a suspender to the RE to lock the resources held by the locks in lock_list
    
    RE: Bluesky run engine 
    
    lock_list: list of lock objects
    
    """
    
    ipython_session_id = os.getpid() 
    
    if 'user_name' in RE.md:
    
        user_string = RE.md['user_name'] + ' ' + str(ipython_session_id) +' ' + RE.md['hostname']
    else:
    
        user_string =str(ipython_session_id) +' ' + RE.md['hostname']
    
    if lock_list != None:
        for lock in lock_list:
            suspender = SuspendWhenChanged(lock.user, expected_value=user_string, allow_resume=True)
            RE.install_suspender(suspender)

            #Take the resource
            if (lock.free.get() != 1) and (lock.user.get() != user_string):
                print(f"{lock.name} is in use by {lock.user.get()}, contact them to unlock")
            else:
                lock.lock(user_string)
                print(f"{lock.name} has been locked to {user_string}")




        

  
        
        
  



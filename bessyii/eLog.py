from bessyii.locks import teardown_my_shell,lock_resource
from getpass import getpass
import Levenshtein as lev
import requests
import logging
import json
from datetime import datetime, timedelta
from bluesky.callbacks import CallbackBase
from pprint import pformat
import time


def requestInvestigationName(username,password):
    """Use a username and password to request all the investigations available to the user, then ask the user to select one


    Args:
        username (str): the username like :code:`qqu`
        password (str): the password

    Returns:
        title (str): the title of the investigation
        name (str): the investigation id
        id_num (str): the eLog id number
        full_name (str): the username of the user
        
    """    
    session_id, full_name = getSessionID(username,password)
    
    if session_id == None:
        
        print("Authentication Failed\n")
        return None, None, None

    url = 'https://icat.helmholtz-berlin.de/icatplus/catalogue/'+session_id+'/investigation'
    header = {'Content-Type': 'application/json'}
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    
    code = 403
    while code != 200:
        try:
            response = requests.get(url, headers=header, proxies=proxies)
            code = response.status_code
            if code != 200:
                #assumes that retrying will work and theat the session_id is valid
                print(f"error code= {code}, retrying")
                response.raise_for_status()

            elif code == 200:
                response_data = json.loads(response.text)
                
        
        except:
             pass
            
            


    #Request the title or some of it, or the investigation id

    possible_investigations = []
    
    part_title = input(f"\nEnter part or all of the investigation title or ID: ")

    while len(possible_investigations) == 0:
        for item in response_data:

            title = str(item['title'])
            id_num = str(item['name'])
            Distance = lev.distance(title.lower(),part_title.lower())
            Ratio = lev.ratio(title.lower(),part_title.lower())

            if part_title in title or part_title.lower() in title.lower() or Ratio > 0.8 or Distance < 10 or part_title in id_num:
                possible_investigations.append(item)

        index_sel = 1
        if len(possible_investigations) >1:
            print(f"Here are the investigations we found ")
            for i, investigation in enumerate(possible_investigations):
                print(f"    {i+1}. {investigation['title']}")

            index_sel = int(input(f"\nWhich is the correct investigtion: "))
        if len(possible_investigations) >=1:    
            title = possible_investigations[index_sel-1]['title']
            name = possible_investigations[index_sel-1]['name'].split(':')[1]
            id_num = possible_investigations[index_sel-1]['id']
        else:
            print(f"\nNo Investiagtions Found")
            part_title = input(f"\nEnter part or all of the investigation title or ID, or enter 'exit' to abort search: ") 
            if part_title == 'exit':
                return None, None, None
 
    return title, name, id_num, full_name



def getSessionID(username, password):
    """Use a username and password to get a session id and the full name of the user

    Args:
        username (string): the username like qqu
    password : string
        password (string): the password

    Returns:
        session_id (str): the session id string used to authenticate an eLog session
        full_name (str): the username of the user
    """    

    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    header = {'Content-Type': 'application/json'}
    data = {"plugin":"hzbrex","username":username,"password":password}
    session_id = None
    full_name = None
    code = 403
    while code != 200:
        try:
            response = requests.post('https://icat.helmholtz-berlin.de/icatplus/session', headers=header,data=json.dumps(data), proxies=proxies)
            code = response.status_code
            if code == 403:
        
                print("Authentication Failed")
                username =str(input("username: "))
                password = str(getpass())
                data = {"plugin":"hzbrex","username":username,"password":password}
                        
            elif code != 200:
                print(f"error code= {code}, retrying")
                response.raise_for_status()

            elif code == 200:
                
                response_data = json.loads(response.text)
                
                session_id = response_data['sessionId']
                full_name = response_data['fullName']
                if session_id and full_name:
                    print(f"SessionID is {session_id}, Full Name is {full_name}")
                    return session_id, full_name
                else:
                    print("Error requesting session ID. Response is None. Retrying")
        
        except:
             pass


def writeToELog(message, investigation_id, session_id = '9987e109-fc74-4e1d-8d5a-d5e518686534'  ):
    """use a username and password to write a message to a particular eLog investigation

    Args:
        message (string): the message to be written    
        investigation_id (string): the elog investigation id as returned by requestInvestigationName (id_num)
        session_id (str, optional): used to authenticate. Defaults to '9987e109-fc74-4e1d-8d5a-d5e518686534'.

    Returns:
        response.status_code(int): the http response code, 200 is good
    """    

    # make a new comment with the machine tag
    now = datetime.now()-timedelta(hours=2)

    dt_string = now.strftime("%m/%d/%Y %H:%M:%S") # Note the American format.
    html_event_with_tag ={
    "type":"annotation",
    "category":"comment",
    "content":[
        {
            "text":"<p>"+str(message)+"</p>",
            "format":"html"
    }],
    "creationDate":dt_string,
    "tag": [
    "60deb980e105e3001a3daa2a"
    ]
    } # The tag is used to write "machine"

    #get session id
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/' + session_id + '/investigation/id/'+ str(investigation_id)+ '/event/create'
    header = {'Content-Type': 'application/json'}
    data = html_event_with_tag
    
    
    code = 403
    attempts = 0
    while code != 200 and attempts<10:
        try:
            response = requests.post(url, headers=header,data=json.dumps(data), proxies=proxies)
            code = response.status_code
                        
            if code != 200:
                print(f"error code= {code}, retrying")
                response.raise_for_status()

        except:
             attempts = attempts +1 
        
        time.sleep(1)
            
            
    

    return response.status_code

########### -------- Callbacks


class ELogCallback(CallbackBase):

    """
    A callback which writes to the eLog. To be called by RE. 

    Assumes that it's only handling one document stream at a time
    If the start document doesn't contain a key 'eLog_id_num' nothing is 
    written and the callback does nothing

    Args:
        db (_type_): databroker catalog
        start_template (_type_): template to be written when start document is produced
        baseline_template (_type_): template to be written when baseline is recorded
        stop_template (_type_): template to be written when stop document is produced 

    """
    def __init__(self,db,start_template,baseline_template,stop_template):
        """
        Args:
            db (_type_): databroker catalog
            start_template (_type_): template to be written when start document is produced
            baseline_template (_type_): template to be written when baseline is recorded
            stop_template (_type_): template to be written when stop document is produced
        """        
        self._descriptors = {}
        self._initial_baseline_config = {}
        self._baseline_toggle = True
        self._eLog_id_num = None
        self._db = db
        self._start_template = start_template
        self._baseline_template = baseline_template
        self._stop_template = stop_template

    def start(self, doc):
        """To be Documented

        Args:
            doc (_type_): _description_
        """        
        if 'eLog_id_num' in doc:
            self._eLog_id_num = doc['eLog_id_num']
            writeToELog(self._start_template.render(doc),self._eLog_id_num)
            
    def descriptor(self, doc):
        """To be Documented

        Args:
            doc (_type_): _description_
        """        
        self._descriptors[doc['uid']] = doc
        for key in doc['configuration']:
            self._initial_baseline_config = { **self._initial_baseline_config, **doc['configuration'][key]['data']}
        
    def event(self, doc):
        """To be Documented

        Args:
            doc (_type_): _description_
        """        
        
        descriptor = self._descriptors[doc['descriptor']]     
        
        if descriptor.get('name') == 'baseline':
            self._baseline_toggle = not self._baseline_toggle

            if not self._baseline_toggle:
                
                if self._eLog_id_num != None:
                    
                    writeToELog(self._baseline_template.render({ **doc['data'], **self._initial_baseline_config}),self._eLog_id_num)
               
            
        # Do something
    def stop(self, doc):
        """To be Documented

        Args:
            doc (_type_): _description_
        """        
        if self._eLog_id_num != None:
            writeToELog(self._stop_template.render(doc),self._eLog_id_num)
            self._eLog_id_num = None
                

    def clear(self):
        """To be Documented
        """        
        self._baseline_toggle = True
        self._eLog_id_num = None
        self._descriptors.clear()
        self._initial_baseline_config.clear()

###### log in and out functions:

  

def authenticate_session(RE,db,lock_list=None):
    """Authenticate to an eLog session (Note that db is passed but not used...)

    Args:
        RE (_type_): run engine object
        db (_type_): databroker catalog
        lock_list (_type_, optional): list of resource locks. Defaults to None.

    """    

    if 'eLog_id_num' in RE.md:
        print("Already logged in")
        return
    
    username =str(input("username: "))
    password = str(getpass())
    title, name, id_num, full_name= requestInvestigationName(username,password)
    if title == None or name == None or id_num == None:
        return None
    
    name_list = full_name.split()
    full_name = name_list[0][0].upper() +'. '+ name_list[-1]

    print(f"Data will now be saved in ICAT with investigation: \n\n name:   {title} \n\n ID:   {name}")
    print(f"\n\nYou can reach the eLog here: https://icat.helmholtz-berlin.de/datahub/investigation/{id_num}/events")

    RE.md['investigation_title']=title
    RE.md['investigation_id'] = name
    RE.md['eLog_id_num'] = id_num
    RE.md['user_profile'] = username
    RE.md['user_name'] = full_name

    if lock_list!=None:
        lock_resource(RE,lock_list)

    

def logout_session(RE,lock_list=None):
    """Log out from a elog session

    Args:
        RE (_type_): run engine object
        lock_list (_type_, optional): list of resource locks. Defaults to None.
    """      
    if lock_list!=None:
        teardown_my_shell(RE,lock_list)
        
    if 'eLog_id_num' not in RE.md:
        print(eLog_sub_id)
        print("No eLog Connected")
        return
    
    else:
        
        
        #Clear the metadata
        
        print(f"disconnected from eLog {RE.md['investigation_title']}")
        
        if 'investigation_title' in RE.md:
            del RE.md['investigation_title']

        if 'investigation_id' in RE.md:
            del RE.md['investigation_id']

        if 'eLog_id_num' in RE.md:
            del RE.md['eLog_id_num']

        if 'user_profile' in RE.md:
            del RE.md['user_profile']
        
        if 'user_name' in RE.md:
            del RE.md['user_name']

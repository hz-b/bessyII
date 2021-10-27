from getpass import getpass
import Levenshtein as lev

def requestInvestigationName(username,password):

    session_id, full_name = getSessionID(username,password)
    
    if session_id == None:
        
        print("Authentication Failed\n")
        return None, None, None

    url = 'https://icat.helmholtz-berlin.de/icatplus/catalogue/'+session_id+'/investigation'
    header = {'Content-Type': 'application/json'}
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    response = requests.get(url, headers=header, proxies=proxies)
    response_data = (json.loads(response.text))


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

import requests
import logging
import json
from datetime import datetime, timedelta
from bluesky.callbacks import CallbackBase
from pprint import pformat

def getInvestigationIDFromTitle(session_id, title_string):
    url = 'https://icat.helmholtz-berlin.de/icatplus/catalogue/'+session_id+'/investigation'
    header = {'Content-Type': 'application/json'}
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    response = requests.get(url, headers=header, proxies=proxies)
    response_data = (json.loads(response.text))
    for item in response_data:
        title = str(item['title'])
        #Select the id with the title Test: ingest for SISSY
        if title == title_string:
            investigation_id = str(item['id'])
            
    return investigation_id

def getInvestigationIDFromName(session_id, name_string):
    url = 'https://icat.helmholtz-berlin.de/icatplus/catalogue/'+session_id+'/investigation'
    header = {'Content-Type': 'application/json'}
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    response = requests.get(url, headers=header, proxies=proxies)
    response_data = (json.loads(response.text))
    for item in response_data:
        name = str(item['name'])
        #Select the id with the title Test: ingest for SISSY
        if name_string in name:
            investigation_id = str(item['id'])
            
    return investigation_id

def getSessionID(username, password):
    proxies = {"http": "http://www.bessy.de:3128", "https": "http://www.bessy.de:3128"}
    header = {'Content-Type': 'application/json'}
    data = {"plugin":"hzbrex","username":username,"password":password}
    
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

            else:
                
                response_data = json.loads(response.text)
                
                session_id = response_data['sessionId']
                full_name = response_data['fullName']
                return session_id, full_name
        
        except:
             pass


def writeToELog(message, username, password, investigation_id ):
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
    session_id, full_name = getSessionID(username,password)

    url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/' + session_id + '/investigation/id/'+ str(investigation_id)+ '/event/create'
    header = {'Content-Type': 'application/json'}
    data = html_event_with_tag
    response = requests.post(url, headers=header,data=json.dumps(data), proxies=proxies)

    return response.status_code



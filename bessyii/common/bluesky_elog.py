import requests
import logging
import json
from datetime import datetime
from bluesky.callbacks import CallbackBase

def writeToELog(message):
    # make a new comment with the machine tag
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
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
    }

    #Only works with valid key
    url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/52f0ec92-b79c-4a9e-bac0-afc923ef0dd9/investigation/id/7645/event/create'
    header = {'Content-Type': 'application/json'}
    data = html_event_with_tag
    response = requests.post(url, headers=header,data=json.dumps(data))

    return response.status_code



class MyELogCallback(CallbackBase):
    def start(self, doc):
        print("I got a new 'start' Document")
        writeToELog("starting a plan")
        # Do something
    def descriptor(self, doc):
        print("I got a new 'descriptor' Document")
        # Do something
    def event(self, doc):
        print("I got a new 'event' Document")
        # Do something
    def stop(self, doc):
        print("I got a new 'stop' Document")
        writeToELog("plan complete")
        # Do something
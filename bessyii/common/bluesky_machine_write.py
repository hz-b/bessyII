




import requests
import logging
import json

from getpass import getpass

username =str(input("username: "))
password = str(getpass())


# These two lines enable debugging at httplib level (requests->urllib3->http.client)
# You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# The only thing missing will be the response.body which is not logged.
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
http_client.HTTPConnection.debuglevel = 1

# You must initialize logging, otherwise you'll not see debug output.
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

#test we can reach the server
response = requests.get('https://icat.helmholtz-berlin.de/icatplus/')
print(response.text)

#now try and get our details and session id 
header = {'Content-Type': 'application/json'}
data = {"plugin":"hzbrex","username":username,"password":password}

response = requests.post('https://icat.helmholtz-berlin.de/icatplus/session', headers=header,data=json.dumps(data))
response_data = json.loads(response.text)
print(response.status_code)
print(response.text)
print(response_data)

## Get all the investigations you are a member of
#curl 'https://icat.helmholtz-berlin.de/icatplus/catalogue/<SESSION_ID>/investigation' -H 'Content-Type: application/json;charset=utf-8'

session_id = response_data['sessionId']
print('Session ID is: ' + session_id)
url = 'https://icat.helmholtz-berlin.de/icatplus/catalogue/'+session_id+'/investigation'
header = {'Content-Type': 'application/json'}


response = requests.get(url, headers=header)
response_data = (json.loads(response.text))[0]
investigation_id = str(response_data['id'])
print('the investigation id is: ' + investigation_id)

from datetime import datetime

# datetime object containing current date and time
now = datetime.now()
 
print("now =", now)
dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

plain_text_event ={
"type":"annotation",
"category":"comment",
"content":[
    {
	"text":"This is a comment message sent from python",
        "format":"plainText"
}],
"creationDate":dt_string
}

now = datetime.now()
dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

html_event ={
"type":"annotation",
"category":"comment",
"content":[
    {
        "text":"<p>This is a comment message</p>",
        "format":"html"
}],
"creationDate":dt_string
}

## Send a plain text comment
#curl -d '{"category": "annotation", "content": [{"text":"this is a comment messagt", "format":"plainText"}]}' -H "Content-Type: application/json" -X POST https://icat.helmholtz-berlin.de/icatplus/logbook/<SESSION_ID>/investigation/id/<INVESTIGATION_ID>/event/create

url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/'+ session_id +'/investigation/id/'+ investigation_id +'/event/create'
header = {'Content-Type': 'application/json'}
data = plain_text_event

response = requests.post(url, headers=header,data=json.dumps(data))
print(response.status_code)

data = html_event
response = requests.post(url, headers=header,data=json.dumps(data))
print(response.status_code)


##tags
url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/'+ session_id +'/investigation/id/'+ investigation_id +'/tag'
header = {'Content-Type': 'application/json'}


response = requests.get(url, headers=header,data=json.dumps(data))
print(response.status_code)
print(json.loads(response.text))



# make a new comment with the machine tag
now = datetime.now()
dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
html_event_with_tag ={
"type":"annotation",
"category":"comment",
"content":[
    {
        "text":"<p>This is a comment message from python with a tag</p>",
        "format":"html"
}],
"creationDate":dt_string,
"tag": [
  "60deb980e105e3001a3daa2a"
]
}

url = 'https://icat.helmholtz-berlin.de/icatplus/logbook/'+ session_id +'/investigation/id/'+ investigation_id +'/event/create'
header = {'Content-Type': 'application/json'}
data = html_event_with_tag
response = requests.post(url, headers=header,data=json.dumps(data))
print(response.status_code)
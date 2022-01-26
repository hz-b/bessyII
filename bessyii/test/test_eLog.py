import pytest
import bessyii_devices
from bessyii.eLog import writeToELog,ELogCallback
from ophyd.sim import motor, noisy_det
from bluesky.preprocessors import SupplementalData
from jinja2 import Template
from bluesky import RunEngine
from databroker.v2 import temp
from bluesky import Msg

## Set up env


RE = RunEngine({})
db = temp()
RE.subscribe(db.v1.insert)

## Define templates:


start_template ="""
<b> Plan Started by {{user_name}}</b>
<br> Pytest Template
<br>{{- plan_name }} ['{{ uid[:6] }}'] (scan num: {{ scan_id }})
<br>---------
<br>{{ plan_name }}
{% if 'plan_args' is defined %}
    {%- for k, v in plan_args | dictsort %}
        <br>{{ k }}: {{ v }}
    {%-  endfor %}
{% endif %}

<br>---------
<br><b>Sample</b>
{% if sample is defined %}
    {% if sample['name'] is defined %}
        {%- for k, v in sample | dictsort %}
            <br>{{ k }}: {{ v }}
        {%-  endfor %}
    {% else %}
        <br>{{ sample }}
    {% endif %}
{% else %}
    <br> No Sample Given
{% endif %}

<hr style="height:2px;border:none;color:#333;background-color:#333;" />"""


j2_start_template = Template(start_template)


end_template ="""
<hr style="height:2px;border:none;color:#333;background-color:#333;" />
<b>Plan ended</b>
<br>exit_status: {{exit_status}}
<br>num_events: {{num_events}}
<br>uid:{{run_start}}
<br>
<br>{{main_det}} max : {{max_val}}
"""


j2_end_template = Template(end_template)

beamline_status_template ="""
<b>Beamline Status</b>
<br>noisy_det:            {{noisy_det}}
"""
j2_baseline_template = Template(beamline_status_template)


# Create a baseline to test that
sd = SupplementalData()

sd.baseline = [noisy_det]
RE.preprocessors.append(sd)

# Subscribe our callback
RE.subscribe(ELogCallback(db,j2_start_template,j2_baseline_template,j2_end_template))

## define the checks

def write_check():
    
    message = "eLog pytest message"
    response = writeToELog(message, 7645)
    
    return response == 200

### implement the tests

def test_write():
    assert write_check() == True
    
def test_callback():
    
    RE.md['eLog_id_num'] = '7645'
    RE([Msg('open_run', plan_args={}), Msg('close_run')])
    
    #we can't assert anything, but we can at least check it runs. 
    # You should check that somthing is written to the elog!




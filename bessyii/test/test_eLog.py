#test eLog Writer

import pytest
import bessyii_devices
from bessyii.eLog import writeToELog

#Cannot test the functions that require username and password

def write_check():
    
    message = "eLog pytest message"
    response = writeToELog(message, 7645)
    
    return response == 200


def test_write():
    assert write_check() == True
    

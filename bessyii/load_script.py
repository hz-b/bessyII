

from IPython import get_ipython
ipython = get_ipython()

import os

def prepend_line(file_name, line):
    """ Insert given string as a new line at the beginning of a file """
    # define name of temporary dummy file
    dummy_file = file_name + '.bak'
    # open original file in read mode and dummy file in write mode
    with open(file_name, 'r') as read_obj, open(dummy_file, 'w') as write_obj:
        # Write given line to the dummy file
        write_obj.write(line + '\n')
        # Read lines from original file one by one and append them to the dummy file
        for line in read_obj:
            write_obj.write(line)
    # remove original file
    os.remove(file_name)
    # Rename dummy file as the original file
    os.rename(dummy_file, file_name)



def compare(a, b):
    """
    Compare two strings character by character.
    Returns False if at least one pair of charcaters differs.
    """
    result = True
    for x, y in zip(a, b):
        if x != y:
             result=False
    return result
         
class simple_load():
    """
    A class to simply load the user scripts into ipython
    when the class is instantied in the ipython profile
    in the file tools.py
    instantiate with 
      from .base import *
      from bessyii.load_script import simple_load
      SL = simple_load(user_script_location='/home/....../bluesky/user_scripts/',
                 user_ns_location='/home/...../.ipython/profile_root/startup/BEAMLINE/user_ns/')
      load_user_script = SL.load_script

    then use with:
    
      load_user_script(file_path_within_user_script_folder)
    
    Parameters
        ----------
        user_script_location : string
            absolute path to user script folder, terminate with /
        user_ns_location : string
            absolute path to user_ns folder in ipython profile, terminate with /
        base : string, optional
            name of the base file, if different
        beamline : string, optional
            name of the beamline file, if different
        plans : string, optional
            name of the plans file, if different
    """
    def __init__(self, user_script_location, user_ns_location, beamline='beamline', plans='plans', custom_lines = None):
        self.user_script_location = user_script_location
        self.user_ns_location     = user_ns_location
        self.beamline    = beamline
        self.plans       = plans
        self.lines = ["# start of automatically prepended lines",
                      'import sys', 
                      "sys.path.append('"+self.user_ns_location+"')", 
                      "from "+self.beamline+" import *",
                      "from "+self.plans+" import *",
                      "from IPython import get_ipython",
                      "user_ns = get_ipython().user_ns"
                      ]
        if custom_lines != None:
            for cl in custom_lines:
                self.lines.append(cl)
        self.lines.append("# end of automatically prepended lines")
        self.lines.reverse()
    def load_script(self,filepath_within_usl):
        # assemble the path to the file
        path_to_file = self.user_script_location+filepath_within_usl
        #read the first line of the file and compare it to
        # the last element in lines (it was reversed, so would be the first)
        # If they are different then I prepend lines to the text file
        with open(path_to_file) as f:
            first_line = f.readline()
        # check if we already prepended the lines
        comparison = compare(first_line, self.lines[-1])
        if comparison == False:
            for line in self.lines:
                prepend_line(path_to_file, line)
        ipython.magic("run "+path_to_file)




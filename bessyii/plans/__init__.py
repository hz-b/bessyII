# reimport commonly used scan for backward compatibility
# previously they were copied in here and were "hacked" to inject 
# "command_elog" metadata string in them
from bluesky.plans import count,scan,grid_scan




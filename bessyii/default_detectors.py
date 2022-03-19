#bluesky imports
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky import RunEngine
from ophyd import Kind

#define the plan wrapper
from bluesky.preprocessors import (
    plan_mutator,
    single_gen,
    ensure_generator,
)
from bluesky.utils import Msg

#this is basically the monitor_during_wrapper so ensure the message order works
def change_kind(plan, signals):
    if 'detectors' in plan.gi_frame.f_locals:
        silent_sig = [sig for sig in signals if sig not in plan.gi_frame.f_locals['detectors']]
        start_msgs = [Msg('init_silent', sig) for sig in silent_sig]
        close_msgs = [Msg('close_silent', sig) for sig in silent_sig]
        plan.gi_frame.f_locals['detectors'] += silent_sig

        def insert_after_open(msg):
            if msg.command == 'open_run':
                def new_gen():
                    yield from ensure_generator(start_msgs)
                return single_gen(msg), new_gen()
            else:
                return None, None

        def insert_before_close(msg):
            if msg.command == 'close_run':
                def new_gen():
                    yield from ensure_generator(close_msgs)
                    yield msg
                return new_gen(), None
            else:
                return None, None

        # Apply nested mutations.
        plan1 = plan_mutator(plan, insert_after_open)
        plan2 = plan_mutator(plan1, insert_before_close)
        return (yield from plan2)
    
    else:
        
        return (yield from plan)

#make sure the SupplementalData uses the wrapper
from bluesky.preprocessors import (
    SupplementalData,
    baseline_wrapper,
)

class SupplementalDataSilentDets(SupplementalData):
    def __init__(self, *args, silent_devices = [], **kwargs):
        super().__init__(*args, **kwargs)
        self.silent_devices = silent_devices
        
    def __call__(self, plan):
        plan = change_kind(plan, self.silent_devices)
        plan = baseline_wrapper(plan, self.baseline)
        return(yield from plan)

#custom methods for the RunEngine to set the kind

from ophyd import Kind
async def init_silent(msg):
    
    for signal in msg.obj.get_instantiated_signals():
        sig = signal[1] #since it's a tuple
        
        #check if it's a read attr, and that it's hinted. I include this line to deal with detectors which don't have val as their read_attr name
        if sig.attr_name in msg.obj.read_attrs and sig.kind == Kind.hinted:
    
            sig.kind = Kind.normal
    
async def close_silent(msg):
    
    
    for signal in msg.obj.get_instantiated_signals():
        sig = signal[1] #since it's a tuple
        
        if sig.attr_name in msg.obj.read_attrs and sig.kind == Kind.normal:
    
            sig.kind = Kind.hinted

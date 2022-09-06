#bluesky imports
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky import RunEngine
from ophyd import Kind, Signal, Device

#define the plan wrapper
from bluesky.preprocessors import (
    plan_mutator,
    single_gen,
    ensure_generator,
    inject_md_wrapper
    
)
from bluesky.utils import Msg

#this is basically the monitor_during_wrapper so ensure the message order works
def change_kind(plan, devices):
    if 'detectors' in plan.gi_frame.f_locals:
        silent_det = [dev for dev in devices if not dev in plan.gi_frame.f_locals['detectors']]
        silent_sig = []

        for dev in silent_det:
            if isinstance(dev, Signal):
                silent_sig.append(dev)
            elif isinstance(dev, Device):
                for sig in dev.get_instantiated_signals():
                    if sig[1].attr_name in dev.read_attrs and not sig[1] in silent_sig:
                        silent_sig.append(sig[1])                
            else:
                print(f"{type(dev)} is not supported yet.")

        signal_kinds = {sig: sig.kind for sig in silent_sig}
        start_msgs = [Msg('init_silent', sig, kind=signal_kinds[sig]) for sig in silent_sig]
        close_msgs = [Msg('close_silent', sig, kind=signal_kinds[sig]) for sig in silent_sig]
        plan.gi_frame.f_locals['detectors'] += silent_det

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

class BessySupplementalData(SupplementalDataSilentDets):
    """
    Extends the above class allowing us to add metadata from a PV automatically to all plans
    """
    def __init__(self, *args, light_status,beamline_name = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.light_status = light_status
        self.beamline_name = beamline_name
        
    def __call__(self, plan):
        status_string = self.light_status.get()
        
        if self.beamline_name:
            status_string = str(self.beamline_name) +'_'+ status_string
            
        plan = inject_md_wrapper(plan, {"beamline_status" :status_string})
        plan = change_kind(plan, self.silent_devices)
        plan = baseline_wrapper(plan, self.baseline)
        return(yield from plan)
    
#custom methods for the RunEngine to set the kind

from ophyd import Kind
async def init_silent(msg):
    msg.kwargs['kind'] = msg.obj.kind
    msg.obj.kind = Kind.normal

async def close_silent(msg):    
    msg.obj.kind = msg.kwargs['kind']

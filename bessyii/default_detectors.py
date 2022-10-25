#bluesky imports
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky import RunEngine
from ophyd import Kind, Signal, Device
from pprint import pprint
#define the plan wrapper
from bluesky.preprocessors import (
    
    single_gen,
    ensure_generator,
    inject_md_wrapper,
    stage_wrapper
    
)
import inspect
from bluesky.utils import Msg

from collections import OrderedDict, deque, ChainMap
from collections.abc import Iterable
import uuid
from bluesky.utils import (normalize_subs_input, root_ancestor,
                    separate_devices,
                    Msg, ensure_generator, single_gen,
                    short_uid as _short_uid, make_decorator,
                    RunEngineControlException, merge_axis)
from functools import wraps
from bluesky.plan_stubs import (open_run, close_run, mv, pause, trigger_and_read)


def plan_mutator(plan, msg_proc):
    """
    Alter the contents of a plan on the fly by changing or inserting messages.

    Parameters
    ----------
    plan : generator

        a generator that yields messages (`Msg` objects)
    msg_proc : callable
        This function takes in a message (or additionally the previous message) 
        and specifies messages(s) to replace it with.
        
        The function must account for what type of response the
        message would prompt. For example, an 'open_run' message causes the
        RunEngine to send a uid string back to the plan, while a 'set' message
        causes the RunEngine to send a status object back to the plan. The
        function should return a pair of generators ``(head, tail)`` that yield
        messages. The last message out of the ``head`` generator is the one
        whose response will be sent back to the host plan. Therefore, that
        message should prompt a response compatible with the message that it is
        replacing. Any responses to all other messages will be swallowed. As
        shorthand, either ``head`` or ``tail`` can be replaced by ``None``.
        This means:

        * ``(None, None)`` No-op. Let the original message pass through.
        * ``(head, None)`` Mutate and/or insert messages before the original
          message.
        * ``(head, tail)`` As above, and additionally insert messages after.
        * ``(None, tail)`` Let the original message pass through and then
          insert messages after.

        The reason for returning a pair of generators instead of just one is to
        provide a way to specify which message's response should be sent out to
        the host plan. Again, it's the last message yielded by the first
        generator (``head``).
        

    Yields
    ------
    msg : Msg
        messages from `plan`, altered by `msg_proc`

    See Also
    --------
    :func:`bluesky.plans.msg_mutator`
    """
    # internal stacks
    msgs_seen = dict()
    msgs_seen_list = []
    plan_stack = deque()
    result_stack = deque()
    tail_cache = dict()
    tail_result_cache = dict()
    exception = None

    parent_plan = plan
    ret_value = None
    # seed initial conditions
    plan_stack.append(plan)
    result_stack.append(None)

    while True:
        # get last result
        if exception is not None:
            # if we have a stashed exception, pass it along
            try:
                msg = plan_stack[-1].throw(exception)
            except StopIteration as e:
                # discard the exhausted generator
                exhausted_gen = plan_stack.pop()
                # if this is the parent plan, capture it's return value
                if exhausted_gen is parent_plan:
                    ret_value = e.value

                # if we just came out of a 'tail' generator,
                # discard its return value and replace it with the
                # cached one (from the last message in its paired
                # 'new_gen')
                if id(exhausted_gen) in tail_result_cache:
                    ret = tail_result_cache.pop(id(exhausted_gen))

                result_stack.append(ret)
                

                if id(exhausted_gen) in tail_cache:
                    gen = tail_cache.pop(id(exhausted_gen))
                    if gen is not None:
                        plan_stack.append(gen)
                        saved_result = result_stack.pop()
                        tail_result_cache[id(gen)] = saved_result
                        # must use None to prime generator
                        result_stack.append(None)

                if plan_stack:
                    
                    continue
                else:
                    return ret_value
            except Exception as e:
                # if we catch an exception,
                # the current top plan is dead so pop it
                plan_stack.pop()
                if plan_stack:
                    # stash the exception and go to the top
                    exception = e
                    continue
                else:
                    raise
            else:
                exception = None
        else:
            ret = result_stack.pop()
            try:
                
                msg = plan_stack[-1].send(ret)
               
            except StopIteration as e:
                # discard the exhausted generator
                exhausted_gen = plan_stack.pop()
                # if this is the parent plan, capture it's return value
                if exhausted_gen is parent_plan:
                    ret_value = e.value

                # if we just came out of a 'tail' generator,
                # discard its return value and replace it with the
                # cached one (from the last message in its paired
                # 'new_gen')
                if id(exhausted_gen) in tail_result_cache:
                    ret = tail_result_cache.pop(id(exhausted_gen))

                result_stack.append(ret)

                if id(exhausted_gen) in tail_cache:
                    gen = tail_cache.pop(id(exhausted_gen))
                    if gen is not None:
                        plan_stack.append(gen)
                        saved_result = result_stack.pop()
                        tail_result_cache[id(gen)] = saved_result
                        # must use None to prime generator
                        result_stack.append(None)

                if plan_stack:
                    continue
                else:
                    return ret_value
            except Exception as ex:
                # we are here because an exception came out of the send
                # this may be due to
                # a) the plan really raising or
                # b) an exception that came out of the run engine via ophyd

                # in either case the current plan is dead so pop it
                failed_gen = plan_stack.pop()
                if id(failed_gen) in tail_cache:
                    gen = tail_cache.pop(id(failed_gen))
                    if gen is not None:
                        plan_stack.append(gen)
                # if there is at least
                if plan_stack:
                    exception = ex
                    continue
                else:
                    raise ex
        # if inserting / mutating, put new generator on the stack
        # and replace the current msg with the first element from the
        # new generator
        if id(msg) not in msgs_seen:
            
            msgs_seen[id(msg)] = msg
            
            # Use the id as a hash, and hold a reference to the msg so that
            # it cannot be garbage collected until the plan is complete.
            
            # Additionally keep track of all previous messages
            msgs_seen_list.append(msg)
            args_list = inspect.getfullargspec(msg_proc)
            args_num = len(args_list[0])
   
            #if msg_proc has two arguements, give it the previous message as the second
            if args_num == 1:
                new_gen, tail_gen = msg_proc(msg)
            elif args_num == 2:
                if len(msgs_seen) >2 :
                    new_gen, tail_gen = msg_proc(msg,msgs_seen_list[-2])
                else:
                    new_gen, tail_gen = msg_proc(msg,msgs_seen_list[-1])
            # mild correctness check
            if tail_gen is not None and new_gen is None:
                new_gen = single_gen(msg)
            if new_gen is not None:
                # stash the new generator
                plan_stack.append(new_gen)
                # put in a result value to prime it
                result_stack.append(None)
                # stash the tail generator
                tail_cache[id(new_gen)] = tail_gen
                # go to the top of the loop
                continue

        try:
            # yield out the 'current message' and collect the return
            inner_ret = yield msg
        except GeneratorExit:
            # special case GeneratorExit.  We must clean up all of our plans
            # and exit with out yielding anything else.
            for p in plan_stack:
                p.close()
            raise
        except Exception as ex:
            if plan_stack:
                exception = ex
                continue
            else:
                raise
        else:

            result_stack.append(inner_ret)







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
        #plan.gi_frame.f_locals['detectors'] += silent_det
        
    
        def insert_trigger_before_wait_after_trigger(msg, last_msg):
            if msg.command == 'wait' and last_msg.command == "trigger":
                #find the group
                group = last_msg.kwargs['group']
                trigger_msgs = [Msg('trigger', sig, group=group) for sig in silent_sig]
                def new_gen():
                    yield from ensure_generator(trigger_msgs)
                    yield msg
                return new_gen(), None
            else:
                return None, None
                
        def insert_read_before_read_after_create(msg, last_msg):
            if msg.command == 'read' and last_msg.command == "create":

                read_msgs = [Msg('read', sig) for sig in silent_sig]
                def new_gen():
                    yield from ensure_generator(read_msgs)
                    yield msg
                return new_gen(), None
            else:
                return None, None

        
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
        plan2 = plan_mutator(plan1, insert_read_before_read_after_create)
        plan3 = plan_mutator(plan2, insert_trigger_before_wait_after_trigger)
        plan4 = plan_mutator(plan3, insert_before_close)

        #Find all devices without parents in the detectors list

        silent_device_parents = separate_devices(root_ancestor(device) for device in devices)
        detector_device_parents = separate_devices(root_ancestor(device) for device in plan.gi_frame.f_locals['detectors'])

        different_parents = [device for device in silent_device_parents if not device in detector_device_parents]
        #finally, stage the silent_det list
        plan5 = stage_wrapper(plan4,different_parents)
        return (yield from plan5)
    
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
    def __init__(self, *args, light_status=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.light_status = light_status
        
    def __call__(self, plan):
        status_string = " "
        if self.light_status:
            status_string = self.light_status.get()
        

            
        plan = inject_md_wrapper(plan, {"end_station" :status_string})
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

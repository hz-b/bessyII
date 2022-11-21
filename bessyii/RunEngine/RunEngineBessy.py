from bluesky.run_engine import RunEngine
import asyncio
try:
    from asyncio import current_task
except ImportError:
    # handle py < 3,7
    from asyncio.tasks import Task
    current_task = Task.current_task
    del Task

class RunEngineBessy(RunEngine):
    """RunEngine modifications at BESYYII


    """    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    
        self.register_command("restore",self._restore)

    async def _restore(self, msg):
        """
        restore a device and cache the returned status object.

        Expected message object is

            Msg('restore', obj, *args, **kwargs)

        where arguments are passed through to `obj.restore(*args, **kwargs)`.
        """
        kwargs = dict(msg.kwargs)
        group = kwargs.pop('group', None)
        self._movable_objs_touched.add(msg.obj)

        if hasattr(msg.obj, "restore"):

            ret = msg.obj.restore(*msg.args, **kwargs)
            p_event = asyncio.Event(loop=self._loop_for_kwargs)
            pardon_failures = self._pardon_failures

            def done_callback(status=None):
                self.log.debug("The object %r reports restore is done "
                            "with status %r", msg.obj, ret.success)
                self._loop.call_soon_threadsafe(
                    self._status_object_completed, ret, p_event, pardon_failures)


            if ret: #if we are actually moving any movers
                
                ret.add_callback(done_callback)

                self._groups[group].add(p_event.wait)
                self._status_objs[group].add(ret)

                return ret


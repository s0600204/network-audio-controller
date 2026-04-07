import asyncio
from collections.abc import Coroutine
from concurrent.futures import Future as ConcurrentFuture # Not to be confused with asyncio.Future
from threading import Thread


class DanteApplication:

    def __init__(self, *_, run_as_lib: bool = True):
        self._event_loop: asyncio.loop = asyncio.new_event_loop()
        self._event_loop.set_debug(True)

        self._run_as_lib: bool = run_as_lib
        self._thread: Thread | None = None

    @property
    def event_loop(self) -> asyncio.loop:
        return self._event_loop

    def run_task(self, coro: Coroutine) -> ConcurrentFuture:
        return asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def start(self) -> None:
        if self._event_loop.is_running():
            return

        def run_event_loop():
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.run_forever()

        if self._run_as_lib and not self._thread:
            self._thread = Thread(target=run_event_loop)
            self._thread.start()
        else:
            run_event_loop()

    def stop(self) -> None:
        if self._event_loop.is_running():
            async def stop_loop():
                self._event_loop.stop()
            self.run_task(stop_loop())

        if self._thread:
            self._thread.join()
            self._thread = None

    def test(self) -> None:
        self.run_task(test())

async def test():
    for idx in range(5):
        print('beta', idx)
        await asyncio.sleep(1)

import asyncio
from collections.abc import Coroutine
from threading import Thread
from typing import TYPE_CHECKING

from .arc_service import DanteARCService
from .cmc_service import DanteCMCService
from .dbc_service import DanteDBCService
from .discovery import DanteDiscovery
from .device import DanteDevice
from .metering_service import DanteMeteringService
from .settings_service import DanteSettingsService
from .util.consts import LOGGER

if TYPE_CHECKING:
    from concurrent.futures import Future as ConcurrentFuture # Not to be confused with asyncio.Future

    from .channel import DanteTxChannel


class DanteApplication:

    def __init__(self, *_, run_as_lib: bool = True):
        self._event_loop: asyncio.loop = asyncio.new_event_loop()
        self._event_loop.set_debug(True)

        self._run_as_lib: bool = run_as_lib
        self._thread: Thread | None = None

        self._arc_service: DanteARCService = DanteARCService(self)
        self._cmc_service: DanteCMCService = DanteCMCService(self)
        self._dbc_service: DanteDBCService = DanteDBCService(self)
        self._mtr: DanteMeteringService = DanteMeteringService(self)
        self._settings: DanteSettingsService = DanteSettingsService(self)
        self._discovery: DanteDiscovery = DanteDiscovery(self)

        self._devices: list[DanteDevice] = []
        self._orphaned_tx_channels: dict[str, list[DanteTxChannel]] = {}

    @property
    def arc_service(self) -> DanteARCService:
        return self._arc_service

    @property
    def cmc_service(self) -> DanteCMCService:
        return self._cmc_service

    @property
    def dbc_service(self) -> DanteDBCService:
        return self._dbc_service

    @property
    def devices(self) -> list[DanteDevice]:
        return self._devices

    @property
    def event_loop(self) -> asyncio.loop:
        return self._event_loop

    @property
    def metering_service(self) -> DanteMeteringService:
        return self._mtr

    @property
    def settings_service(self) -> DanteSettingsService:
        return self._settings

    def append_orphaned_tx_channel(self, tx_device_name: str, tx_channel: DanteTxChannel) -> None:
        if tx_device_name not in self._orphaned_tx_channels:
            self._orphaned_tx_channels[tx_device_name] = []
        self._orphaned_tx_channels[tx_device_name].append(tx_channel)

    def get_device_by_name(self, device_name: str) -> DanteDevice | None:
        if not device_name:
            return None
        # Names are unique on the network, but case-insensitive
        device_name = device_name.lower()
        try:
            return next(
                filter(
                    lambda device: device.name.lower() == device_name,
                    self._devices
                )
            )
        except StopIteration:
            return None

    async def register_device(self, device_spec):
        LOGGER.info("Discovered new Dante device at %s", device_spec['ipv4'])
        new_device = DanteDevice(self, device_spec)
        self._devices.append(new_device)

    def retrieve_orphaned_tx_channel(self, tx_device_name: str, tx_channel_name: str) -> DanteTxChannel | None:
        if tx_device_name not in self._orphaned_tx_channels:
            return None
        for idx in range(len(self._orphaned_tx_channels[tx_device_name])):
            channel = self._orphaned_tx_channels[tx_device_name][idx]
            if channel.name == tx_channel_name:
                return self._orphaned_tx_channels[tx_device_name].pop(idx)
        return None

    def run_task(self, coro: Coroutine) -> ConcurrentFuture:
        return asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def start(self) -> None:
        if self._event_loop.is_running():
            return

        self.run_task(self._arc_service.start())
        self.run_task(self._cmc_service.start())
        # ~ self.run_task(self._dbc_service.start())
        self.run_task(self._discovery.start())
        self.run_task(self._mtr.start())
        self.run_task(self._settings.start())

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
                await self._arc_service.stop()
                await self._cmc_service.stop()
                # ~ await self._dbc_service.stop()
                await self._discovery.stop()
                await self._mtr.stop()
                await self._settings.stop()
                await self._event_loop.stop()
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

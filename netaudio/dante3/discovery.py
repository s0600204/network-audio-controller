import asyncio
import enum
import ipaddress
from typing import TYPE_CHECKING

from zeroconf import IPVersion
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncServiceInfo,
    AsyncZeroconf,
)

from .arc_service import DanteARCService
from .cmc_service import DanteCMCService
from .dbc_service import DanteDBCService
from .util.consts import LOGGER

if TYPE_CHECKING:
    from zeroconf import Zeroconf

    from .application import DanteApplication


class DanteDiscoveryState(enum.Enum):
    COMPLETE = enum.auto()
    DISCONNECTED = enum.auto()
    IN_PROGRESS = enum.auto()


class DanteDiscovery:

    DISCOVERABLE_SERVICE_CLASSES: list = [
        DanteARCService,
        DanteCMCService,
        DanteDBCService,
    ]
    REQUEST_TIMEOUT = 1000 # ms

    def __init__(self, application: DanteApplication):
        self._app: DanteApplication = application
        self._found: dict = {}
        self._tasks: set[asyncio.Task] = set()
        self._zc: AsyncZeroconf | None = None
        self._zc_browser: AsyncServiceBrowser | None = None

    def add_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ) -> None:
        task = asyncio.create_task(
            self._add_service(zc_instance, service_type, service_name),
            name=f"Add {service_name}"
        )
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)

    async def _add_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ):
        info = AsyncServiceInfo(service_type, service_name)
        await info.async_request(zc_instance, self.REQUEST_TIMEOUT)
        if not info:
            LOGGER.error(
                "Unable to get info for added service (%s, %s)",
                service_type, service_name,
            )
            return

        name = info.server
        LOGGER.debug("Device %s (%s) appeared", name, service_name)

        if name not in self._found:
            self._found[name] = {
                **{service.SERVICE_TYPE_SHORT: None for service in self.DISCOVERABLE_SERVICE_CLASSES},
                'ipv4': ipaddress.IPv4Address(info.parsed_addresses()[0]),
                'status': DanteDiscoveryState.IN_PROGRESS,
            }
        elif self._found[name]['status'] == DanteDiscoveryState.DISCONNECTED:
            self._found[name]['status'] = DanteDiscoveryState.IN_PROGRESS
            for service in self.DISCOVERABLE_SERVICE_CLASSES:
                self._found[name][service.SERVICE_TYPE_SHORT] = None

        dante_service = self.get_dante_service_from_type(service_type)
        service_descriptor = dante_service.build_service_descriptor(info)
        self._found[name][dante_service.SERVICE_TYPE_SHORT] = service_descriptor

        def _all_present():
            for service in self.DISCOVERABLE_SERVICE_CLASSES:
                if self._found[name][service.SERVICE_TYPE_SHORT] is None:
                    return False
            return True

        if _all_present():
            if self._found[name]['status'] == DanteDiscoveryState.IN_PROGRESS:
                self._found[name]['status'] = DanteDiscoveryState.COMPLETE
                await self._app.register_device(self._found[name])

    def get_dante_service_from_type(self, service_type: str):
        for service in self.DISCOVERABLE_SERVICE_CLASSES:
            if service.SERVICE_TYPE_MDNS == service_type:
                return service
        return None

    def remove_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ) -> None:
        task = asyncio.create_task(
            self._remove_service(zc_instance, service_type, service_name),
            name=f"Remove {service_name}"
        )
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)

    async def _remove_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ) -> None:
        info = AsyncServiceInfo(service_type, service_name)
        await info.async_request(zc_instance, self.REQUEST_TIMEOUT)
        if not info:
            LOGGER.error(
                "Unable to get info for removed service (%s, %s)",
                service_type, service_name,
            )
            return

        name = info.server
        LOGGER.debug("Device %s (%s) disappeared", name, service_name)

    async def start(self) -> None:
        if self._zc and self._zc.zeroconf.started:
            return
        self._zc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        service_types = [service.SERVICE_TYPE_MDNS for service in self.DISCOVERABLE_SERVICE_CLASSES]
        self._zc_browser = AsyncServiceBrowser(
            self._zc.zeroconf,
            service_types,
            self
        )
        LOGGER.log("Started Dante Discovery")

    async def stop(self) -> None:
        if not self._zc or not self._zc.zeroconf.started:
            return
        await self._zc_browser.async_cancel()
        await self._zc.async_close()
        # ~ LOGGER.log("Stopped Dante Discovery") # Stops thread from joining (if .log, or .debug; .warning works fine)

    def update_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ) -> None:
        task = asyncio.create_task(
            self._update_service(zc_instance, service_type, service_name),
            name=f"Update {service_name}"
        )
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)

    async def _update_service(
        self,
        zc_instance: Zeroconf,
        service_type: str,
        service_name: str
    ) -> None:
        info = AsyncServiceInfo(service_type, service_name)
        await info.async_request(zc_instance, self.REQUEST_TIMEOUT)
        if not info:
            LOGGER.error(
                "Unable to get info for updated service (%s, %s)",
                service_type, service_name,
            )
            return

        name = info.server
        LOGGER.debug("Device %s (%s) updated", name, service_name)

        # ~ dante_service = self.get_dante_service_from_type(service_type)
        # ~ service_descriptor = dante_service.build_service_descriptor(info)
        # ~ self._found[name][dante_service.SERVICE_TYPE_SHORT] = service_descriptor

import asyncio
from enum import Enum
from typing import TYPE_CHECKING

from .util.consts import LOGGER
from .util.helpers import bytes2int

if TYPE_CHECKING:
    from zeroconf import ServiceInfo as MDNSServiceInfo

    from .application import DanteApplication


class MessageType(bytes, Enum):
    SEND = b'\x00\x00'
    RECV = b'\x00\x01'
    PAGI = b'\x81\x12'


class TransactionIndex:
    _num: int = 0

    def generate(self) -> int:
        self._num = self._num + 1
        return self._num


class _DanteService:

    SERVICE_HEADER_LENGTH: int
    SERVICE_PORT: str
    SERVICE_TYPE_SHORT: str

    def __init__(self, application: DanteApplication):
        self._app: DanteApplication = application

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError


class DanteDiscoverableService:

    SERVICE_TYPE_MDNS: str

    @classmethod
    def build_service_descriptor(cls, mdns_service_info: MDNSServiceInfo) -> None:
        raise NotImplementedError


class DanteUnicastProtocol(asyncio.DatagramProtocol):

    AWAIT_FOR_TIMEOUT = 2 # seconds

    def __init__(self):
        self._pending: dict[tuple[str, int], asyncio.Future] = {}
        self._transport: asyncio.DatagramTransport | None = None

    def connection_lost(self, exc: Exception | None) -> None:
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def datagram_received(
        self,
        data: bytes,
        addr: tuple[str, int]
    ) -> None:
        transaction_idx = bytes2int(data[4:6])
        future = self._pending.get((addr, transaction_idx), None)
        if not future:
            LOGGER.warning(
                "Message received (from %s:%i) that wasn't in answer to anything: %s",
                addr[0], addr[1], data,
            )
            return

        future.set_result(data)

    async def request(
        self,
        message: bytes,
        destination: tuple[str, int],
        transaction_idx: int,
    ) -> bytes | None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        key = (destination, transaction_idx)
        self._pending[key] = future

        self._transport.sendto(message, destination)
        try:
            return await asyncio.wait_for(future, self.AWAIT_FOR_TIMEOUT)
        except asyncio.TimeoutError:
            LOGGER.error("Request Timed Out (%s)", key)
            return None
        finally:
            self._pending.pop(key)


class DanteUnicastService(_DanteService):

    def __init__(self, application: DanteApplication):
        super().__init__(application)
        self._protocol: asyncio.DatagramProtocol | None = None
        self._transaction_index: TransactionIndex = TransactionIndex()
        self._transport: asyncio.DatagramTransport | None = None

    async def start(self):
        self._transport, self._protocol = await self._app.event_loop.create_datagram_endpoint(
            DanteUnicastProtocol,
            local_addr=("0.0.0.0", 0),
        )

    async def stop(self):
        if self._transport:
            self._transport.close()
            self._transport = None

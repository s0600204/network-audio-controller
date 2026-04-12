import asyncio
from enum import Enum
from ipaddress import IPv4Address
import socket
import struct
from typing import TYPE_CHECKING

import ifaddr

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


class DanteMulticastProtocol(asyncio.DatagramProtocol):

    def __init__(self, callback: callable):
        self._callback: callable = callback
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def datagram_received(
        self,
        data: bytes,
        addr: tuple[str, int]
    ) -> None:
        self._callback(IPv4Address(addr[0]), data)


class DanteMulticastService(_DanteService):

    SERVICE_MCAST_GRP: str | None = None

    _ignored_addrs: list[str] = ['127.0.0.1']

    def __init__(self, application: DanteApplication):
        super().__init__(application)
        self._protocol: asyncio.DatagramProtocol | None = None
        self._transport: asyncio.DatagramTransport | None = None

    def _build_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.SERVICE_PORT))

        for adapter in ifaddr.get_adapters():
            for addr in adapter.ips:
                if not addr.is_IPv4 or addr.ip in self._ignored_addrs:
                    LOGGER.debug("Not binding to %s on %s", addr.ip, addr.nice_name)
                    continue
                mreq = struct.pack("4s4s", socket.inet_aton(self.SERVICE_MCAST_GRP), socket.inet_aton(addr.ip))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        return sock

    def _receive(
        self,
        ipv4_addr: IPv4Address,
        message: bytes,
    ) -> None:
        raise NotImplementedError

    async def start(self):
        self._transport, self._protocol = await self._app.event_loop.create_datagram_endpoint(
            lambda: DanteMulticastProtocol(self._receive),
            sock=self._build_socket(),
        )

    async def stop(self):
        if self._transport:
            self._transport.close()
            self._transport = None


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

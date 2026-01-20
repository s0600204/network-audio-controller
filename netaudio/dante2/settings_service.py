# ~ from __future__ import annotations
# ~ from typing import TYPE_CHECKING

from .channel import DanteChannelType
from .service import DanteUnicastService
from .util import (
    NULL_HEXTET,
    # ~ decode_integer,
    # ~ decode_string,
    encode_integer,
    # ~ encode_string,
    encode_mac_address,
    get_mac_addr_serving_ipv4,
)

# ~ if TYPE_CHECKING:
from .device import DanteDevice
from .util import (
    PCMEncoding,
    SampleRate,
)


class DanteSettingsServiceDescriptor:
    pass


class DanteSettingsService(DanteUnicastService):
    """
    Multicast Control and Monitoring
    """
    SERVICE_HEADER_LENGTH: int = 32
    SERVICE_PORT: int = 8700
    SERVICE_TYPE_MDNS: None = None
    SERVICE_TYPE_SHORT = 'settings'

    def command(
        self,
        device: DanteDevice,
        command_code: bytes,
        command_body: tuple[bytes],
    ) -> None:
        ipv4 = device.ipv4
        mac_address = get_mac_addr_serving_ipv4(device.ipv4)
        message_idx = self._message_index.generate()

        command = b''.join((
            b'\xff\xff',
            NULL_HEXTET,                        # message length, calculated below
            encode_integer(message_idx),
            NULL_HEXTET,                        # observed alternate values: \x03\xe4, \x02\x9f, \xab\xcd
            encode_mac_address(mac_address),
            NULL_HEXTET,                        # message type/direction?
            b'Audinate',                        # no null terminator
            b'\x07\x38',                        # possibly a protocol version; observed values: \x07\x27, \x07\x31, \x07\x34, \x07\x38
            command_code,
            NULL_HEXTET * 2,                    # second hextet sometimes observed as \x00\x64
            *command_body,
        ))
        command = command[:2] + encode_integer(len(command)) + command[4:]

        self._message_store[message_idx] = {
            'device': device,
            'command': command,
        }
        self._send_queue.put(((str(ipv4), self.SERVICE_PORT), command))

    def get_dante_model(
        self,
        device: DanteDevice,
    ):
        code = b'\x00\x61'
        body = ()
        self.command(device, code, body)

    def get_make_model(
        self,
        device: DanteDevice,
    ):
        code = b'\x00\xc1'
        body = ()
        self.command(device, code, body)

    def set_aes67(
        self,
        device: DanteDevice,
        is_enabled: bool,
    ):
        code = b'\x10\x06'
        body = (
            b'\x00\x01',
            encode_integer(is_enabled),
        )
        self.command(device, code, body)

    def set_gain_level(
        self,
        device: DanteDevice,
        channel_type: DanteChannelType,
        channel_number: int,
        gain_level: int
    ):
        code = b'\x10\x0a'
        body = (
            b'\x00\x01',
            b'\x00\x01',
            b'\x00\x0c',
            b'\x00\x10',
            b'\x01x\02' if channel_type == DanteChannelType.RX else b'\x02\x01',
            NULL_HEXTET * 2,
            encode_integer(channel_number),
            NULL_HEXTET,
            encode_integer(gain_level),
        )
        self.command(device, code, body)

    def set_pcm_encoding(
        self,
        device: DanteDevice,
        encoding: PCMEncoding,
    ):
        code = b'\x00\x83'
        body = (
            NULL_HEXTET,
            b'\x00\x01',
            encoding.encode(),
        )
        self.command(device, code, body)

    def set_sample_rate(
        self,
        device: DanteDevice,
        sample_rate: SampleRate
    ):
        code = b'\x00\x81'
        body = (
            NULL_HEXTET,
            b'\x00\x01',
            sample_rate.encode(),
        )
        self.command(device, code, body)

    def trigger_identify(self, device: DanteDevice):
        code = b'\x00\x63'
        body = ()
        self.command(device, code, body)

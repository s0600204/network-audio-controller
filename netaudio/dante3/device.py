import struct
from typing import TYPE_CHECKING

from .channel import (
    DanteChannelType,
    DanteRxChannel,
    DanteTxChannel,
)
from .subscription import (
    DanteSubscription,
    DanteSubscriptionStatus,
)
from .util.consts import (
    NULL_HEXTET,
    LOGGER,
)
from .util.enums import (
    Latency,
    PCMEncoding,
    SampleRate,
)
from .util.helpers import (
    bytes2int,
    decode_protocol_version,
    decode_string,
    decode_version,
)

if TYPE_CHECKING:
    from ipaddress import IPv4Address

    from .application import DanteApplication
    from .arc_service import DanteARCServiceDescriptor
    from .cmc_service import DanteCMCServiceDescriptor
    from .dbc_service import DanteDBCServiceDescriptor
    from .util.types import (
        ChannelCounts,
        ChannelContainer,
    )



class DanteDevice:

    def __init__(self, application: DanteApplication, service_descriptors: dict):
        self._app: DanteApplication = application
        self._service_descriptors = service_descriptors

        self._latency: Latency | None = None
        self._name: str = ''
        self._pcm_encoding: PCMEncoding | None = None
        self._sample_rate: SampleRate | None = None

        self._channel_counts: ChannelCounts = {DanteChannelType.RX: 0, DanteChannelType.TX: 0}
        self._channels: ChannelContainer = {DanteChannelType.RX: [], DanteChannelType.TX: []}

        self._dante_info: dict = {
            'abbr_name': (),
            'full_name': (),
            'dante_fw_version': (),
            'hardware_fw_version': (),
            'rom_version': (),
        }
        self._device_info: dict = {
            'manu_name_short': (),
            'manu_name_full': (),
            'model': (),
            'software_version': (),
            'firmware_version': (),
            'product_version': (),
            'product_version_str': (),
        }

        self._app.run_task(self._async_init())

    async def _async_init(self) -> None:
        """
        Initial series of requests for data
        """
        ## From arc service:
        await self._request_device_info()

        ## From settings service:
        # Dante Info
        await self._app.settings_service.transmit(self, b'\x00\x61', ())
        # Model Info
        await self._app.settings_service.transmit(self, b'\x00\xc1', ())

        await self._request_name()

        await self._request_latency()

        await self._request_channel_counts()
        # These three require the above, but then should be able to be runnable at the same time
        await self._request_rx_channels()
        await self._request_tx_channels()
        if self.arc.protocol_version < (2, 8, 2):
            await self._request_tx_channels_friendly()

    @property
    def arc(self) -> DanteARCServiceDescriptor:
        return self._service_descriptors['arc']

    @property
    def cmc(self) -> DanteCMCServiceDescriptor:
        return self._service_descriptors['cmc']

    @property
    def dbc(self) -> DanteDBCServiceDescriptor:
        return self._service_descriptors['dbc']

    @property
    def ipv4(self) -> IPv4Address:
        return self._service_descriptors['ipv4']

    @property
    def latency(self) -> Latency:
        return self._latency

    @latency.setter
    def latency(self, latency: Latency|float|int) -> None:
        if not isinstance(latency, Latency):
            try:
                latency = Latency(latency)
            except ValueError:
                LOGGER.error("Unrecognised Latency value: %f", latency)
                return
        self._app.run_task(self._set_latency(latency))

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        # TODO: validate new name:
        # * max. 31 chars
        # * chars: `a-zA-Z0-9` and literals `-`
        # * may not start or end with `-`
        # * unique on network
        self._app.run_task(self._set_name(new_name))

    @property
    def pcm_encoding(self) -> PCMEncoding:
        return self._pcm_encoding

    @pcm_encoding.setter
    def pcm_encoding(self, encoding: PCMEncoding | int) -> None:
        if isinstance(encoding, int):
            try:
                encoding = PCMEncoding(encoding)
            except ValueError:
                LOGGER.error("Unrecognised Encoding value: %s", encoding)
                return
        self._app.run_task(self._app.settings_service.set_pcm_encoding(self, encoding))

    @property
    def rx_channels(self):
        return self._channels[DanteChannelType.RX]

    @property
    def sample_rate(self) -> SampleRate:
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, sample_rate: SampleRate | int) -> None:
        if isinstance(sample_rate, int):
            try:
                sample_rate = SampleRate(sample_rate)
            except ValueError:
                LOGGER.error("Unrecognised Sample Rate value: %s", sample_rate)
                return
        self._app.run_task(self._app.settings_service.set_sample_rate(self, sample_rate))

    @property
    def tx_channels(self):
        return list(
            filter(
                lambda chan: chan.number > 0,
                self._channels[DanteChannelType.TX]
            )
        )

    @property
    def versions(self) -> dict:
        def _join(version: tuple) -> str:
            return '.'.join(str(x) for x in version)
        return {
            'arc': _join(self.arc.protocol_version),
            'cmc': _join(self.cmc.protocol_version),
            'dante_firmware': _join(self._dante_info['dante_fw_version']),
            'dante_hardware': _join(self._dante_info['hardware_fw_version']),
            'dante_rom': _join(self._dante_info['rom_version']),
            'device_firmware': _join(self._device_info['firmware_version']),
            'device_product': self._device_info['product_version_str'],
            'device_software': _join(self._device_info['software_version']),
        }

    def get_channel_by_name(self, channel_type: DanteChannelType, channel_name: str) -> DanteRxChannel | DanteTxChannel | None:
        # Names are unique on the device, but case-insensitive
        channel_name = channel_name.lower()
        try:
            return next(
                filter(
                    lambda chan: chan.name.lower() == channel_name,
                    self._channels[channel_type]
                )
            )
        except StopIteration:
            return None

    def get_channel_by_number(self, channel_type: DanteChannelType, channel_number: int) -> DanteRxChannel | DanteTxChannel | None:
        try:
            return next(
                filter(
                    lambda chan: chan.number == channel_number,
                    self._channels[channel_type]
                )
            )
        except StopIteration:
            return None

    def handle_notification_dante_info(self, payload: bytes):
        self._dante_info['abbr_name'] = decode_string(payload, 12)
        self._dante_info['full_name'] = decode_string(payload, 56)
        self._dante_info['dante_fw_version'] = decode_version(payload, 0, 34)
        self._dante_info['hardware_fw_version'] = decode_version(payload, 4, 38)
        self._dante_info['rom_version'] = decode_version(payload, 40)

    def handle_notification_model_info(self, payload: bytes):
        self._device_info['manu_name_short'] = decode_string(b'\x00' + payload, 1)
        self._device_info['manu_name_full'] = decode_string(payload, 44)
        self._device_info['model'] = decode_string(payload, 172)
        self._device_info['software_version'] = decode_version(payload, 24)
        self._device_info['firmware_version'] = decode_version(payload, 28)
        # ~ self._device_info['product_version'] = decode_version(payload, 300)
        self._device_info['product_version_str'] = decode_string(payload, 304)

        # This appears to be the same as what's provided under the 'model' key of the ARC and CMC
        # mDNS service information.
        self._device_info['other'] = decode_string(payload, 8)

    def json(self) -> None:
        return {
            "name": self._name,
            "ipv4": str(self.ipv4),
            "channel_count": [
                self._channel_counts[DanteChannelType.RX],
                self._channel_counts[DanteChannelType.TX],
            ],
            "arc_version": '.'.join([str(x) for x in self.arc.protocol_version]),
            "cmc_version": '.'.join([str(x) for x in self.cmc.protocol_version]),
            "sample_rate": self._sample_rate.value if self._sample_rate else None,
            # ~ "rx_channels": self.rx_channels,
            # ~ "tx_channels": self.tx_channels,
        }

    async def _request_channel_counts(self) -> None:
        response = await self._app.arc_service.request(self, b'\x10\x00', ())
        self._channel_counts = {
            DanteChannelType.RX: bytes2int(response[14:16]),
            DanteChannelType.TX: bytes2int(response[12:14]),
        }

    async def _request_device_info(self) -> None:
        response = await self._app.arc_service.request(self, b'\x10\x03', ())

        """ The following information matches that which is found in the ARC and CMC mDNS service information """
        info = {
            'device_name': decode_string(response, bytes2int(response[22:24])), # or 26:28
            'device_name_alt': decode_string(response, bytes2int(response[26:28])), # ...see?
            'server_name': decode_string(response, bytes2int(response[24:26])), # sans .local
            'arc_proto_vers': decode_protocol_version(response, 40),
            'arc_proto_min': decode_protocol_version(response, 42),
            'arc_router': decode_version(response, 36),
            'cmc_proto_vers': decode_protocol_version(response, 44),
            'arc_router_info': decode_string(response, bytes2int(response[16:18])),
            'arc_router_debug': decode_string(response, bytes2int(response[18:20])),
        }

    def request_latency(self) -> None:
        self._app.run_task(self._request_latency())

    async def _request_latency(self) -> None:
        opcode = b'\x11\x00'
        # TODO: determine what all these hextets represent below
        payload = (
            b'\x00\x12', # or b'\x00\x13' ## number of hextets in payload (after this one)?
            b'\x02\x01',
            b'\x82\x04',
            b'\x82\x05',
            b'\x02\x10',
            b'\x02\x11',
            b'\x82\x18',
            b'\x82\x19',
            b'\x83\x01',
            b'\x83\x02',
            b'\x83\x06',
            b'\x03\x10',
            b'\x03\x11',
            b'\x03\x03',
            b'\x80\x21',
            b'\x00\xf0',
            b'\x80\x60',
            b'\x00\x22',
            b'\x00\x63',
                         # b'\x00\x64'
        )
        response = await self._app.arc_service.request(self, opcode, payload)
        new_latency = Latency.decode(
            response,
            bytes2int(response[22:24])
        )
        if new_latency and new_latency != self._latency:
            self._latency = new_latency
            # TODO: latency has changed: emit event?

    def request_name(self) -> None:
        self._app.run_task(self._request_name())

    async def _request_name(self) -> None:
        response = await self._app.arc_service.request(self, b'\x10\x02', ())
        if not response or len(response) < self._app.arc_service.SERVICE_HEADER_LENGTH:
            return
        strlen = response.find(b'\x00', 10)
        self._name = response[10:strlen].decode('ascii')

    def request_rx_channels(self) -> None:
        self._app.run_task(self._request_rx_channels())

    async def _request_rx_channels(self) -> None:
        protocol_version = self.arc.protocol_version
        rx_count = self._channel_counts[DanteChannelType.RX]

        for page in range(1): # TODO: fix page numbers
            if protocol_version >= (2, 8, 2):
                opcode = b'\x34\x00'
                # TODO: One of the \x00\x01 hextets is the page num. Determine which one.
                payload = (
                    NULL_HEXTET * 3,
                    b'\x00\x01',
                    b'\x00\x01',
                    b'\x00\x01',
                    NULL_HEXTET * 6,
                )
            else:
                opcode = b'\x30\x00'
                payload = (
                    b'\x00\x01',
                    struct.pack('>H', (page << 4) + 1),
                    NULL_HEXTET,
                )

            response = await self._app.arc_service.request(self, opcode, payload)

            if protocol_version >= (2, 8, 2):
                max_count, current_count = struct.unpack('BB', response[16:18])
            else:
                max_count, current_count = struct.unpack('BB', response[10:12])

            # Properties common to all channels on this device
            # (Location of this is specified inside each specific channel definition)
            common_definition = None

            for index in range(current_count):
                if protocol_version >= (2, 8, 2):
                    def_start_ptr = 18
                    definition_length = 56

                    start = def_start_ptr + 2 * index
                    definition_start = bytes2int(response[start:start+2])
                    definition_end = definition_start + definition_length
                    channel_definition = response[definition_start:definition_end]

                    common_definition_ptr = 22

                    rx_channel_name = decode_string(response, bytes2int(channel_definition[20:22]))
                    rx_channel_number = bytes2int(channel_definition[2:4])
                    rx_channel_status = DanteSubscriptionStatus.derive(
                        bytes2int(channel_definition[50:52])
                    )

                    tx_channel_name = decode_string(response, bytes2int(channel_definition[44:46]))
                    tx_device_name = decode_string(response, bytes2int(channel_definition[46:48]))

                    subscription_status = DanteSubscriptionStatus.derive(
                        bytes2int(channel_definition[48:50])
                    )

                else:
                    def_start = 12
                    definition_length = 16

                    definition_start = def_start + 20 * index
                    definition_end = definition_start + definition_length
                    channel_definition = response[definition_start:definition_end]

                    common_definition_ptr = 4

                    rx_channel_name = decode_string(response, bytes2int(channel_definition[10:12]))
                    rx_channel_number = bytes2int(channel_definition[0:2])
                    rx_channel_status = DanteSubscriptionStatus.derive(
                        bytes2int(channel_definition[12:14])
                    )

                    tx_channel_name = decode_string(response, bytes2int(channel_definition[6:8]))
                    tx_device_name = decode_string(response, bytes2int(channel_definition[8:10]))

                    subscription_status = DanteSubscriptionStatus.derive(
                        bytes2int(channel_definition[14:16])
                    )

                if not common_definition:
                    definition_start = bytes2int(channel_definition[common_definition_ptr:common_definition_ptr+2])
                    definition_end = definition_start + 16
                    common_definition = response[definition_start:definition_end]

                rx_channel = self.get_channel_by_number(DanteChannelType.RX, rx_channel_number)
                if not rx_channel:
                    rx_channel = DanteRxChannel(
                        application = self._app,
                        device = self,
                        number = rx_channel_number,
                        name = rx_channel_name,
                        status = rx_channel_status,
                    )
                    self._channels[DanteChannelType.RX].append(rx_channel)
                    subscription = None
                else:
                    # ~ if rx_channel_name != rx_channel._name:
                        # ~ self._app.events.notify(DanteEventType.CHANNEL_NAME_UPDATED, rx_channel)
                    rx_channel._name = rx_channel_name
                    rx_channel._status = rx_channel_status
                    subscription = rx_channel.subscription

                if not tx_device_name:
                    tx_channel = None
                else:
                    if tx_device_name == '.':
                        tx_device = self
                    else:
                        tx_device = self._app.get_device_by_name(tx_device_name)

                    if tx_device:
                        tx_channel = tx_device.get_channel_by_name(DanteChannelType.TX, tx_channel_name)
                    else:
                        tx_channel = self._app.retrieve_orphaned_tx_channel(tx_device_name, tx_channel_name)

                    if not tx_channel:
                        tx_channel =  DanteTxChannel(
                            application = self._app,
                            device = tx_device or tx_device_name,
                            number = -1, # Not contained within response
                            name = tx_channel_name,
                        )
                        if tx_device:
                            tx_device._channels[DanteChannelType.TX].append(tx_channel)
                        else:
                            self._app.append_orphaned_tx_channel(tx_device_name, tx_channel)

                if not subscription:
                    subscription = DanteSubscription(
                        rx_channel=rx_channel,
                        tx_channel=tx_channel,
                        status=subscription_status,
                    )
                    rx_channel._subscription = subscription
                    if tx_channel:
                        tx_channel._subscriptions.append(subscription)
                else:
                    if subscription.tx_channel:
                        if not tx_channel:
                            subscription.tx_channel._subscriptions.remove(subscription)
                            subscription._tx_channel = None
                        elif subscription.tx_channel != tx_channel:
                            subscription.tx_channel._subscriptions.remove(subscription)
                            subscription._tx_channel = tx_channel
                            tx_channel._subscriptions.append(subscription)
                        # else if both exist and match: do nothing
                    else:
                        if tx_channel:
                            subscription._tx_channel = tx_channel
                            tx_channel._subscriptions.append(subscription)
                        # else if neither exist: do nothing

                    subscription._status = subscription_status

            sample_rate = SampleRate.decode(common_definition, 0)
            if sample_rate and sample_rate != self._sample_rate:
                # TODO: Sample Rate changed - emit event.
                self._sample_rate = sample_rate

    def request_tx_channels(self, friendly_names: bool = False) -> None:
        if friendly_names:
            self._app.run_task(self._request_tx_channels_friendly())
        else:
            self._app.run_task(self._request_tx_channels())

    async def _request_tx_channels(self) -> None:
        protocol_version = self.arc.protocol_version
        tx_count = self._channel_counts[DanteChannelType.TX]

        for page in range(1): # todo: get the other pages of channels
            if protocol_version >= (2, 8, 2):
                opcode = b'\x24\x00'
                # TODO: One of the \x00\x01 hextets is the page num. Determine which one.
                payload = (
                    NULL_HEXTET * 3,
                    b'\x00\x01',
                    b'\x00\x01',
                    b'\x00\x01',
                    NULL_HEXTET * 6,
                )
            else:
                opcode = b'\x20\x00'
                payload = (
                    b'\x00\x01',
                    struct.pack('>H', (page << 4) + 1),
                    NULL_HEXTET,
                )

            response = await self._app.arc_service.request(self, opcode, payload)

            if protocol_version >= (2, 8, 2):
                max_count, num_channels_in_response = struct.unpack('BB', response[16:18])
            else:
                max_count, num_channels_in_response = struct.unpack('BB', response[10:12])

            # Properties common to all channels on this device
            # (Location of this is specified inside each specific channel definition)
            common_definition = None

            for index in range(num_channels_in_response):

                if protocol_version >= (2, 8, 2):
                    definitions_start_ptr = 18
                    definition_length = 40

                    start = definitions_start_ptr + 2 * index
                    definition_start = bytes2int(response[start:start+2])
                    definition_end = definition_start + definition_length
                    channel_definition = response[definition_start:definition_end]

                    if not common_definition:
                        definition_start = bytes2int(channel_definition[22])
                        definition_end = definition_start + 16
                        common_definition = response[definition_start:definition_end]

                    channel_number = bytes2int(channel_definition[2:4])
                    channel_name_default = decode_string(response, bytes2int(channel_definition[30:32]))
                    channel_name_friendly = decode_string(response, bytes2int(channel_definition[20:22]))

                else: ## protocol_version < (2, 8, 2)

                    definitions_start = 12
                    definition_length = 8

                    definition_start = definitions_start + definition_length * index
                    definition_end = definition_start + definition_length
                    channel_definition = response[definition_start:definition_end]

                    if not common_definition:
                        definition_start = bytes2int(channel_definition[4:6])
                        definition_end = definition_start + 16
                        common_definition = response[definition_start:definition_end]

                    channel_number = bytes2int(channel_definition[0:2])
                    channel_name_default = decode_string(response, bytes2int(channel_definition[6:8]))
                    channel_name_friendly = None # Acquired elsewhere

                ## endif protocol_version

                channel = self.get_channel_by_number(DanteChannelType.TX, channel_number)
                if not channel:
                    # If the channel was previously "orphaned", then the channel number won't be known
                    channel = self.get_channel_by_name(DanteChannelType.TX, channel_name_friendly or channel_name_default)
                    if channel:
                        channel._number = channel_number
                    else:
                        # If still not found, the channel is not known
                        channel = DanteTxChannel(
                            application = self._app,
                            device = self,
                            number = channel_number,
                            name = channel_name_friendly or channel_name_default,
                        )
                    self._channels[DanteChannelType.TX].append(channel)
                else:
                    # ~ if channel_name_friendly and channel_name_friendly != channel._name:
                        # ~ self._app.events.notify(DanteEventType.CHANNEL_NAME_UPDATED, channel)
                        # ~ self._app.events.notify(DanteEventType.TRANSMITTERS_CHANGED)
                        # ~ for subscription in channel.subscriptions:
                            # ~ self._app.events.notify(DanteEventType.SUBSCRIPTION_CHANGED, subscription)
                    channel._name = channel_name_friendly or channel_name_default

            sample_rate = SampleRate.decode(common_definition, 0)
            if sample_rate and sample_rate != self._sample_rate:
                # TODO: Sample Rate changed - emit event.
                self._sample_rate = sample_rate

    async def _request_tx_channels_friendly(self) -> None:
        # In theory unnecessary with arc_proto >= 2.8.2, but might prove useful
        tx_count = self._channel_counts[DanteChannelType.TX]
        opcode = b'\x20\x10'
        payload = (
            b'\x00\x01', # start index
            b'\x00\x01', # start channel
            b'\x00\x02', # channel count
        )

        response = await self._app.arc_service.request(self, opcode, payload)
        max_count, num_channels_in_response = struct.unpack('BB', response[10:12])

        definitions_start = 12
        definition_length = 6
        for index in range(num_channels_in_response):
            definition_start = definitions_start + definition_length * index
            definition_end = definition_start + definition_length
            channel_definition = response[definition_start:definition_end]

            channel = self.get_channel_by_number(
                DanteChannelType.TX,
                bytes2int(channel_definition[2:4])
            )

            new_name = decode_string(response, bytes2int(channel_definition[4:6]))
            # ~ if new_name != channel._name:
                # ~ self._app.events.notify(DanteEventType.CHANNEL_NAME_UPDATED, channel)
                # ~ self._app.events.notify(DanteEventType.TRANSMITTERS_CHANGED)
                # ~ for subscription in channel.subscriptions:
                    # ~ self._app.events.notify(DanteEventType.SUBSCRIPTION_CHANGED, subscription)
            channel._name = new_name

    async def _set_name(self, new_name: str) -> None:
        payload = (new_name.encode('ascii') + b'\x00',)
        response = await self._app.arc_service.request(self, b'\x10\x01', payload)
        if response:
            await self._request_name() # New name is not contained within response

    def reset_name(self) -> None:
        self._app.run_task(self._set_name(""))

    async def _set_latency(self, latency: Latency) -> None:
        latency_encoded = latency.encode()

        opcode = b'\x11\x01'
        # TODO: Work out what the other hextets signify
        payload = (
            b'\x05\x03',
            b'\x82\x05',
            struct.pack('>H', self._app.arc_service.SERVICE_HEADER_LENGTH + 22), # location of first `latency_encoded` below
            b'\x02\x11',
            b'\x00\x10',
            b'\x83\x01',
            struct.pack('>H', self._app.arc_service.SERVICE_HEADER_LENGTH + 22 + 4), # location of second `latency_encoded` below
            b'\x82\x19',
            b'\x83\x01',
            b'\x83\x02',
            b'\x83\x06',
            latency_encoded,
            latency_encoded,
        )
        response = await self._app.arc_service.request(self, opcode, payload)

        new_latency = Latency.decode(
            response,
            bytes2int(response[14:16]) # or 22:24
        )
        if new_latency and new_latency != self._latency:
            self._latency = new_latency
            # TODO: latency has changed: emit event?

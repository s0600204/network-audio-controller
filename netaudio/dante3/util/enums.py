from enum import Enum
import struct

from .helpers import bytes2int


class EncodableEnum(Enum):
    @classmethod
    def decode(cls, bytestring: bytes, idx: int):
        value = bytes2int(bytestring[idx : idx + 4])
        try:
            return cls(value)
        except ValueError:
            LOGGER.error("%s is not a recognised value", value)
            return None

    def encode(self) -> bytes:
        return struct.pack('>I', self.value)


class Latency(Enum):
    MS_015  =  0.15
    MS_025  =  0.25
    MS_050  =  0.5
    MS_100  =  1.0
    MS_200  =  2.0
    MS_500  =  5.0
    MS_600  =  6.0
    MS_1000 = 10.0

    @classmethod
    def decode(cls, bytestring: bytes, idx: int):
        value = bytes2int(bytestring[idx : idx + 4]) / 1_000_000
        try:
            return cls(value)
        except ValueError:
            LOGGER.error("%s is not a recognised value", value)
            return None

    def encode(self) -> bytes:
        return struct.pack('>I', self.value * 1_000_000)


class PCMEncoding(EncodableEnum):
    PCM_16 = 16
    PCM_24 = 24
    PCM_32 = 32


class SampleRate(EncodableEnum):
    SR_44100  =  44100
    SR_48000  =  48000
    SR_88200  =  88200
    SR_96000  =  96000
    SR_176400 = 176400
    SR_192000 = 192000

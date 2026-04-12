import codecs
import ipaddress
import socket
import struct
from typing import TYPE_CHECKING
import uuid

import psutil

if TYPE_CHECKING:
    from .types import ProtocolVersion

def bytes2int(source: bytes) -> int:
    if len(source) == 1:
        return struct.unpack('B', source)[0]
    if len(source) == 2:
        return struct.unpack('>H', source)[0]
    if len(source) == 4:
        return struct.unpack('>I', source)[0]
    return -1

def decode_string(source: bytes, ptr: int) -> str:
    if not ptr:
        return None
    substr = source[ptr:]
    if not substr:
        return None
    null_idx = substr.find(b'\x00')
    if null_idx < 0:
        null_idx = len(substr)
    return substr[:null_idx].decode('ascii')

def encode_string(string: str) -> bytes:
    return string.encode('ascii') + b'\x00'

def decode_protocol_version_from_mdns(source: bytes) -> ProtocolVersion:
    '''
    b'1.2.34' => tuple(1, 2, 34)
    '''
    return tuple(
        int(x) for x in source.split(b".")
    )

def decode_protocol_version(source: bytes, ptr: int) -> ProtocolVersion:
    '''
    b'\x12\x34' => tuple(1, 2, 34)
    '''
    protocol_version = source[ptr:ptr + 2].hex()
    return (
        int(protocol_version[0], 16),
        int(protocol_version[1], 16),
        int(protocol_version[2:4], 16),
    )

def encode_protocol_version(protocol_version: ProtocolVersion) -> bytes:
    '''
    tuple(1, 2, 34) => b'\x12\x34'
    '''
    return codecs.decode(
        f"{protocol_version[0]}{protocol_version[1]}{protocol_version[2]:02x}",
        "hex"
    )

def decode_version(source: bytes, ptr: int, ptr2: int|None = None) -> Version:
    '''
    b'\x01\x02\x00\x03' => tuple(1, 2, 3)
      or
    b'\x01\x02\x00\x03' and b'\x00\x04' => tuple(1, 2, 3, 4)
    '''
    version = struct.unpack('>BBH', source[ptr:ptr + 4])
    if ptr2 is not None:
        version = (*version, *struct.unpack('>H', source[ptr2:ptr2+2]))
    return version

def decode_mac_address(source: bytes) -> str:
    '''
    b'\xa1\xb2\xc3\xd4\xe5\xf6' => "a1:b2:c3:d4:e5:f6"
    '''
    return ':'.join(f"{b:02x}" for b in source)

def encode_mac_address(mac_address: str) -> bytes:
    '''
    "A1:B2:C3:D4:E5:F6" => b'\xa1\xb2\xc3\xd4\xe5\xf6'
    '''
    return codecs.decode(''.join(mac_address.split(':')), 'hex')

def get_ip_addr_serving_ipv4(ipv4_address: ipaddress.IPv4Address) -> ipaddress.IPv4Address:
    for adapter in psutil.net_if_addrs().values():
        for nic_address in adapter:
            if nic_address.family == socket.AF_INET: # is IPv4
                network = ipaddress.IPv4Network((nic_address.address, nic_address.netmask), False)
                if ipv4_address in network:
                    return ipaddress.IPv4Address(nic_address.address)

    # TODO: return address of default adapter
    return None

def get_mac_addr_serving_ipv4(ipv4_address: ipaddress.IPv4Address) -> str:
    '''
    Given an IPv4 address, this function determines which local network adapter would be used to
    communicate with it and returns its MAC address.

    Note that we assume that all IPv4 addresses of a network adapter are listed (by `psutil`)
    before the MAC address is.
    '''
    # TODO: Name of this function sucks - think of a better one.
    for adapter in psutil.net_if_addrs().values():
        is_this_adapter = False
        for nic_address in adapter:

            if nic_address.family == socket.AF_INET: # is IPv4
                network = ipaddress.IPv4Network((nic_address.address, nic_address.netmask), False)
                if ipv4_address in network:
                    is_this_adapter = True

            elif nic_address.family == psutil.AF_LINK: # is MAC
                if is_this_adapter:
                    return nic_address.address

    # TODO: return the MAC address of the *default* interface, which the following is not
    # guaranteed to be (see documentation of `uuid.getnode()`)
    return ":".join(f"{b:02x}" for b in uuid.getnode().to_bytes(6, byteorder='big'))

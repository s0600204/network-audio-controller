from .consts import PYTHON_VERSION_TUPLE


if PYTHON_VERSION_TUPLE < (3, 12, 0):
    from typing import TypeAlias
    ChannelContainer: TypeAlias = dict[DanteChannelType.RX: list[DanteRxChannel], DanteChannelType.TX: list[DanteTxChannel]]
    ChannelCounts: TypeAlias = dict[DanteChannelType.RX: int, DanteChannelType.TX: int]
    ProtocolVersion: TypeAlias = tuple[int, int, int]
    Version: TypeAlias = tuple[int, int, int] | tuple[int, int, int, int]

else:
    type ChannelContainer = dict[DanteChannelType.RX: list[DanteRxChannel], DanteChannelType.TX: list[DanteTxChannel]]
    type ChannelCounts = dict[DanteChannelType.RX: int, DanteChannelType.TX: int]
    type ProtocolVersion = tuple[int, int, int]
    type Version = tuple[int, int, int] | tuple[int, int, int, int]

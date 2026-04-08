import logging
import platform


LOGGER = logging.getLogger('netaudio.dante3')
NULL_HEXTET = b'\x00\x00'
PYTHON_VERSION_TUPLE = tuple(int(x) for x in platform.python_version_tuple())

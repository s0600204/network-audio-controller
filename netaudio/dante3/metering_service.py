from .service import DanteUnicastService


class DanteMeteringService(DanteUnicastService):
    """
    Receives and handles level metering messages
    (when such things are requested via CMC)
    """
    SERVICE_PORT: int = 8751
    SERVICE_TYPE_SHORT: str = 'mtr'

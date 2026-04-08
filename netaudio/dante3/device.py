from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ipaddress import IPv4Address

    from .application import DanteApplication
    from .arc_service import DanteARCServiceDescriptor
    from .cmc_service import DanteCMCServiceDescriptor
    from .dbc_service import DanteDBCServiceDescriptor


class DanteDevice:

    def __init__(self, application: DanteApplication, service_descriptors: dict):
        self._app: DanteApplication = application
        self._service_descriptors = service_descriptors

        self._name: str = ''

        # Initial series of requests for data
        self.request_name()

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

    async def _set_name(self, new_name: str) -> None:
        payload = (new_name.encode('ascii') + b'\x00',)
        response = await self._app.arc_service.request(self, b'\x10\x01', payload)
        if response:
            await self._request_name() # New name is not contained within response

    def request_name(self) -> None:
        self._app.run_task(self._request_name())

    async def _request_name(self) -> None:
        response = await self._app.arc_service.request(self, b'\x10\x02', ())
        if not response or len(response) < self._app.arc_service.SERVICE_HEADER_LENGTH:
            return
        strlen = response.find(b'\x00', 10)
        self._name = response[10:strlen].decode('ascii')

    def reset_name(self) -> None:
        self._app.run_task(self._set_name(""))

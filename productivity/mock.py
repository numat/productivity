from collections import defaultdict
from unittest.mock import MagicMock

from pymodbus.bit_read_message import ReadCoilsResponse, ReadDiscreteInputsResponse
from pymodbus.bit_write_message import WriteSingleCoilResponse, WriteMultipleCoilsResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse

from productivity.driver import ProductivityPLC as realProductivityPLC


class AsyncMock(MagicMock):
    """Magic mock that works with async methods"""
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class ProductivityPLC(realProductivityPLC):
    """A version of the driver with the remote communication replaced with local data storage
    for testing"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = AsyncMock()
        self._coils = defaultdict(bool)
        self._discrete_inputs = defaultdict(bool)
        self._registers = defaultdict(bytes)

    async def _request(self, method, *args, **kwargs):
        print(method, args, kwargs)
        print(self._registers)
        if method == 'read_coils':
            address, count = args
            return ReadCoilsResponse([self._coils[address + i] for i in range(count)])
        if method == 'read_discrete_inputs':
            address, count = args
            return ReadDiscreteInputsResponse([self._discrete_inputs[address + i]
                                               for i in range(count)])
        elif method == 'read_holding_registers':
            address, count = args
            return ReadHoldingRegistersResponse([int.from_bytes(self._registers[address + i],
                                                                byteorder='big')
                                                 for i in range(count)])
        elif method == 'write_coil':
            address, data = args
            self._coils[address] = data
            return WriteSingleCoilResponse(address, data)
        elif method == 'write_coils':
            address, data = args
            for i, d in enumerate(data):
                self._coils[address + i] = d
            return WriteMultipleCoilsResponse(address, len(data))
        elif method == 'write_registers':
            address, data = args
            for i, d in enumerate(data):
                self._registers[address + i] = d
            return WriteMultipleRegistersResponse(address, len(data))
        return NotImplementedError(f'Unrecognised method: {method}')

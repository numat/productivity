"""
Python mock driver for AutomationDirect Productivity Series PLCs.

Uses local storage instead of remote communications.

Distributed under the GNU General Public License v2
Copyright (C) 2022 NuMat Technologies
"""

from collections import defaultdict
from unittest.mock import MagicMock

from pymodbus.bit_read_message import ReadCoilsResponse, ReadDiscreteInputsResponse
from pymodbus.bit_write_message import WriteMultipleCoilsResponse, WriteSingleCoilResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse, WriteSingleRegisterResponse

from productivity.driver import ProductivityPLC as realProductivityPLC


class AsyncClientMock(MagicMock):
    """Magic mock that works with async methods."""

    async def __call__(self, *args, **kwargs):
        """Convert regular mocks into into an async coroutine."""
        return super().__call__(*args, **kwargs)


class ProductivityPLC(realProductivityPLC):
    """Mock Productivity driver using local storage instead of remote communication."""

    def __init__(self, address, tag_filepath, timeout=1, *args, **kwargs):
        self.discontinuous_discrete_output = False
        self.tags = self._load_tags(tag_filepath)
        self.addresses = self._calculate_addresses(self.tags)
        self.map = {data['address']['start']: tag for tag, data in self.tags.items()}
        self.client = AsyncClientMock()
        self._coils = defaultdict(bool)
        self._discrete_inputs = defaultdict(bool)
        self._registers = defaultdict(bytes)
        self._register_types = ['holding', 'input']
        self._detect_pymodbus_version()
        if self.pymodbus33plus:
            self.client.close = lambda: None

    async def _request(self, method, *args, **kwargs):
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
        elif method == 'write_register':
            address, data = args
            self._registers[address] = data
            return WriteSingleRegisterResponse(address, data)
        elif method == 'write_registers':
            address, data = args
            for i, d in enumerate(data):
                self._registers[address + i] = d
            return WriteMultipleRegistersResponse(address, len(data))
        return NotImplementedError(f'Unrecognised method: {method}')

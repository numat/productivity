"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from productivity.util import AsyncioModbusClient


class ProductivityPLC(AsyncioModbusClient):
    """Python driver for AutomationDirect Productivity Series PLCs.

    This interface handles the quirks of both Modbus TCP/IP and the PLC,
    abstracting corner cases and providing a simple asynchronous interface.
    """

    async def get_inputs(self, names, start=300001):
        """Get input registers from the PLC.

        Args:
            names: Keys to use when returning the data, as a list of strings.
            start (optional): Starting modbus address.

        >>> plc.get_inputs(['pressure', 'temperature'])
        {'pressure': 5.0, 'temperature': 25.0}

        This uses modbus addresses assigned from the 'Tag Database' window in
        the Productivity PLC software.

        This assumes all registers are 32-bit floats.
        """
        if not 300001 <= start <= 365536:
            raise ValueError("Starting register must be in [300001, 365536].")
        start -= 300001
        count = len(names) * 2
        registers = await self.read_registers(start, count, type='input')
        decoder = BinaryPayloadDecoder.fromRegisters(registers,
                                                     byteorder=Endian.Big,
                                                     wordorder=Endian.Little)
        return {key: decoder.decode_32bit_float() for key in names}

"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
import csv

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from productivity.util import AsyncioModbusClient

data_types = {
    'AIF32': 'float',  # Analog Input Float 32
    'DI': 'bool',      # Discrete Input
    'SBR': 'bool',     # System Boolean Read-only
    'MST': 'bool',     # Module Status biT
    'SSTR': 'str',     # System STRing
    'SWR': 'int',      # System (W)integer Read-only
    'SWRW': 'int'      # System (W)integer Read-Write
}


class ProductivityPLC(AsyncioModbusClient):
    """Driver for AutomationDirect Productivity Series PLCs.

    This interface handles the quirks of both Modbus TCP/IP and the PLC,
    abstracting corner cases and providing a simple asynchronous interface.
    """

    def __init__(self, address, tag_filepath, timeout=1):
        """Initialize PLC connection and data structure.

        Args:
            address: The PLC IP address or DNS name
            tag_filepath: Path to the PLC tags file
            timeout (optional): Timeout when communicating with PLC. Default 1s.
        """
        super().__init__(address, timeout)
        self.tags = self._load_tags(tag_filepath)
        self.addresses = self._calculate_addresses(self.tags)
        self.map = {data['address']['start']: tag for tag, data in self.tags.items()}

    async def get(self):
        """Get values of all tags with assigned modbus addresses.

        Returns:
            A dictionary of {tag: value} pairs.

        """
        result = {}
        if 'coils' in self.addresses:
            result.update(await self._handle_coils())
        for type in ['input', 'holding']:
            if type in self.addresses:
                result.update(await self._handle_registers(type))
        return result

    def get_tags(self):
        """Return all tags and associated configuration information.

        Use this data for debugging or to provide more detailed
        information on user interfaces.

        Returns:
            A dictionary containing information associated with each tag name.

        """
        return self.tags

    async def _handle_coils(self):
        """Handle reading coils from the PLC."""
        result = {}
        coils = await self.read_coils(**self.addresses['coils'])
        current = self.addresses['coils']['address'] + 100001
        end = current + self.addresses['coils']['count']
        for bit in coils.bits:
            if current > end:
                break
            elif current in self.map:
                result[self.map[current]] = bit
            current += 1
        return result

    async def _handle_registers(self, type):
        """Handle reading input or holding registers from the PLC."""
        r = await self.read_registers(**self.addresses[type], type=type)
        decoder = BinaryPayloadDecoder.fromRegisters(r,
                                                     byteorder=Endian.Big,
                                                     wordorder=Endian.Little)
        current = (self.addresses[type]['address'] +
                   (300001 if type == 'input' else 400001))
        end = current + self.addresses[type]['count']
        result = {}
        while current < end:
            if current in self.map:
                tag = self.map[current]
                data_type = self.tags[tag]['type']
                if data_type == 'float':
                    result[tag] = decoder.decode_32bit_float()
                    current += 2
                elif data_type == 'str':
                    result[tag] = decoder.decode_string(50)
                    current += 50
                elif data_type == 'int':
                    result[tag] = decoder.decode_16bit_int()
                    current += 1
                else:
                    raise ValueError("Missing data type.")
            else:
                decoder._pointer += 1
                current += 1
        return result

    def _load_tags(self, tag_filepath):
        """Load tags from file path.

        This tag file is needed to identify the appropriate variable names,
        data types, and modbus addresses. I would love to be able to read
        this directly from the PLC but cannot find any documentation on the
        programming port (9999).
        """
        with open(tag_filepath) as csv_file:
            csv_data = csv_file.read().splitlines()
        csv_data[0] = csv_data[0].lstrip('## ')
        parsed = {
            row['Tag Name'].lower(): {
                'address': {
                    'start': int(row['MODBUS Start Address']),
                    'end': int(row['MODBUS End Address'])
                },
                'id': row['System ID'],
                'comment': row['Comment'],
                'type': data_types.get(
                    row.get('Data Type', row['System ID'].split('-')[0])
                )
            }
            for row in csv.DictReader(csv_data)
            if row['MODBUS Start Address']
        }
        for data in parsed.values():
            if not data['comment']:
                del data['comment']
            if not data['type']:
                raise TypeError(
                    f"{data['id']} is an unsupported data type. Open a "
                    "github issue at numat/productivity to get it added."
                )
        return parsed

    def _calculate_addresses(self, tags):
        """Determine the minimum number of requests to get all tags.

        Modbus limits request length to ~250 bytes (125 registers, 2000 coils).
        We could make this fun and automatic but I don't think most use cases
        need that level of fanciness. I'm leaving it very simple until someone
        tells me it's an issue.
        """
        addresses = sorted([tag['address']['start'] for tag in tags.values()] +
                           [tag['address']['end'] for tag in tags.values()])
        coils = [a for a in addresses if 100000 < a < 165536]
        input_registers = [a for a in addresses if 300000 < a < 365536]
        holding_registers = [a for a in addresses if 400000 < a < 465536]

        output = {}
        if coils:
            start_coil, end_coil = coils[0], coils[-1]
            if end_coil - start_coil > 2000:
                raise ValueError("Only supporting an address span of 2000 coils. "
                                 "If you need more, open a github issue at "
                                 "numat/productivity.")
            output['coils'] = {
                'address': start_coil - 100001,
                'count': end_coil - start_coil + 1
            }
        if input_registers:
            start_register, end_register = input_registers[0], input_registers[-1]
            if end_register - start_register > 2000:
                raise ValueError("Only supporting an address span of 2000 registers. "
                                 "If you need more, open a github issue at "
                                 "numat/productivity.")
            output['input'] = {
                'address': start_register - 300001,
                'count': end_register - start_register + 1
            }
        if holding_registers:
            start_register, end_register = holding_registers[0], holding_registers[-1]
            if end_register - start_register > 2000:
                raise ValueError("Only supporting an address span of 2000 registers. "
                                 "If you need more, open a github issue at "
                                 "numat/productivity.")
            output['holding'] = {
                'address': start_register - 400001,
                'count': end_register - start_register + 1
            }
        return output

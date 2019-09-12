"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
import csv
import pydoc

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder

from productivity.util import AsyncioModbusClient

data_types = {
    'AIF32': 'float',  # Analog Input Float 32-bit
    'F32': 'float',    # Float 32-bit
    'AIS32': 'int32',  # Analog Input (S)integer 32-bit
    'DI': 'bool',      # Discrete Input
    'SBR': 'bool',     # System Boolean Read-only
    'MST': 'bool',     # Module Status biT
    'STR': 'str',      # STRing
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
            result.update(await self._read_coils())
        for type in ['input', 'holding']:
            if type in self.addresses:
                result.update(await self._read_registers(type))
        return result

    def get_tags(self):
        """Return all tags and associated configuration information.

        Use this data for debugging or to provide more detailed
        information on user interfaces.

        Returns:
            A dictionary containing information associated with each tag name.

        """
        return self.tags

    async def set(self, *args, **kwargs):
        """Set tag names to values.

        This function expects keyword arguments. See the below examples.

        >>> set(av1=False)
        >>> set(target=0, setpoint=1.1)
        >>> set(**{'av1': False, 'av2': False})
        """
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                raise ValueError("Remember to unpack! `plc.set(**params)`.")
            else:
                raise TypeError("Unexpected input. See docstring.")
        if not kwargs:
            raise TypeError("Unexpected input. See docstring.")
        to_write = {key.lower(): value for key, value in kwargs.items()}
        unsupported = set(to_write) - set(self.tags)
        if unsupported:
            raise ValueError(f"Missing tags: {', '.join(unsupported)}")
        for key, value in to_write.items():
            data_type = self.tags[key]['type']
            if isinstance(value, int) and data_type == 'float':
                to_write[key] = float(value)
            if not isinstance(value, pydoc.locate(data_type)):
                raise ValueError(f"Expected {key} to be a {data_type}.")
        addresses = [(tag, self.tags[tag]['address']['start']) for tag in to_write]
        sorted(addresses, key=lambda a: a[1])
        if addresses[0][1] < 100000:
            raise ValueError("Unexpected register.")
        while addresses[0][1] < 165536:
            coils = 1
            start = addresses[0][1]
            while addresses[coils][1] == start + coils:
                coils += 1
            values = [to_write[address[0]] for address in addresses[:coils]]
            await self.write_coils(start, values)
            addresses = addresses[coils:]
        if addresses[0][1] < 400000:
            raise ValueError("Cannot write to input registers.")
        while addresses[0][1] < 465536:
            index, registers = 0, 0
            start = addresses[0][1]
            builder = BinaryPayloadBuilder(byteorder=Endian.Big,
                                           wordorder=Endian.Little)
            while addresses[index][1] == start + registers:
                index += 1
                key = addresses[index[0]]
                value = to_write[key]
                data_type = self.tags[key]['type']
                if data_type == 'float':
                    builder.add_32bit_float(value)
                    registers += 2
                elif data_type == 'str':
                    builder.add_string(value.ljust(50))
                    registers += 50
                elif data_type == 'int':
                    builder.add_16bit_int(value)
                    registers += 1
                else:
                    raise ValueError("Missing data type.")
            await self.write_registers(start, builder.build())
            addresses = addresses[index:]
        if addresses:
            raise ValueError("Not all registers spent.")

    async def _read_coils(self):
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

    async def _read_registers(self, type):
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
                    chars = self.tags[tag]['length']
                    result[tag] = decoder.decode_string(chars).decode('ascii')
                    current += (chars + 1) // 2
                elif data_type == 'int':
                    result[tag] = decoder.decode_16bit_int()
                    current += 1
                elif data_type == 'int32':
                    result[tag] = decoder.decode_32bit_int()
                    current += 2
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
                'length': int(row['Number of Characters'] or 0),
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
            if not data['length']:
                del data['length']
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

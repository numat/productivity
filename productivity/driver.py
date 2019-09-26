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
    'S32': 'int32',    # (S)integer 32-bit'
    'C': 'bool',       # (C) Boolean,
    'DI': 'bool',      # Discrete Input
    'DO': 'bool',      # Discrete Output
    'SBR': 'bool',     # System Boolean Read-only
    'MST': 'bool',     # Module Status biT
    'STR': 'str',      # STRing
    'SSTR': 'str',     # System STRing
    'SWR': 'int',      # System (W)integer Read-only
    'SWRW': 'int'      # System (W)integer Read-Write
}
type_start = {
    'discrete_output': 0,
    'discrete_input': 100000,
    'input': 300000,
    'holding': 400000,
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
        if 'discrete_output' in self.addresses:
            result.update(await self._read_discrete(self.addresses['discrete_output']))
        if 'discrete_input' in self.addresses:
            result.update(await self._read_discrete(self.addresses['discrete_input'],
                                                    output=False))

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
        if any([100000 <= x[1] < 400000 for x in addresses]):
            raise ValueError("Cannot write to input registers.")
        addresses.sort(key=lambda a: a[1])

        responses = []
        while addresses and addresses[0][1] < 65536:
            address = addresses.pop(0)
            responses.append(str(await self.write_coil(address[1] - 1,
                                                       to_write[address[0]])))
        while addresses and 400000 <= addresses[0][1] < 465536:
            address = addresses.pop(0)
            builder = BinaryPayloadBuilder(byteorder=Endian.Big,
                                           wordorder=Endian.Little)
            key = address[0]
            value = to_write[key]
            data_type = self.tags[key]['type']
            if data_type == 'float':
                builder.add_32bit_float(value)
            elif data_type == 'str':
                chars = self.tags[key]['length']
                if len(value) > chars:
                    raise ValueError(f'{value} is too long for {key}. '
                                     f'Max: {chars} chars')
                builder.add_string(value.ljust(chars))
            elif data_type == 'int':
                builder.add_16bit_int(value)
            elif data_type == 'int32':
                builder.add_32bit_int(value)
            else:
                raise ValueError("Missing data type.")
            resp = await self.write_registers(address[1] - 400001,
                                              builder.build(),
                                              skip_encode=True)
            responses.append(str(resp[0]))
        if addresses:
            raise ValueError("Not all registers spent.")
        return responses

    async def _read_discrete(self, addresses, output=True):
        """Handle reading coils from the PLC."""
        result = {}
        if output:
            response = await self.read_coils(**addresses)
            current = addresses['address'] + 1
        else:
            response = await self.read_discrete_inputs(**addresses)
            current = addresses['address'] + 100001

        end = current + addresses['count']
        for bit in response.bits:
            if current > end:
                break
            elif current in self.map:
                result[self.map[current]] = bit
            current += 1
        return result

    async def _read_registers(self, a_type):
        """Handle reading input or holding registers from the PLC."""
        r = await self.read_registers(**self.addresses[a_type], type=a_type)
        decoder = BinaryPayloadDecoder.fromRegisters(r,
                                                     byteorder=Endian.Big,
                                                     wordorder=Endian.Little)
        current = self.addresses[a_type]['address'] + type_start[a_type] + 1
        end = current + self.addresses[a_type]['count']
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
                    current += max(chars // 2, 1)
                elif data_type == 'int':
                    result[tag] = decoder.decode_16bit_int()
                    current += 1
                elif data_type == 'int32':
                    result[tag] = decoder.decode_32bit_int()
                    current += 2
                else:
                    raise ValueError("Missing data type.")
            else:
                # Empty modbus addresses or odd length strings could land you on a
                # register that's not used
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
        output = {}
        for a in addresses:
            if 0 < a < 65536:
                a_type = 'discrete_output'
            elif 100000 < a < 165536:
                a_type = 'discrete_input'
            elif 300000 < a < 365536:
                a_type = 'input'
            elif 400000 < a < 465536:
                a_type = 'holding'
            else:
                continue
            if a_type in output:
                output[a_type]['count'] = (a - type_start[a_type]
                                           - output[a_type]['address'])
            else:
                output[a_type] = {'address': a - type_start[a_type] - 1}

        for found_type in output:
            if output[found_type]['count'] > 2000:
                raise ValueError(f"Only supporting an address span of 2000 {found_type}."
                                 " If you need more, open a github issue at "
                                 "numat/productivity.")
        return output

"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2022 NuMat Technologies
"""
import csv
import logging
import pydoc
from copy import deepcopy
from math import ceil
from string import digits
from typing import Any, Dict, List, Optional, Tuple, Union

from pymodbus.bit_write_message import WriteMultipleCoilsResponse, WriteSingleCoilResponse
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.pdu import ExceptionResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse

from productivity.util import DATA_TYPES, TYPE_START, AsyncioModbusClient


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
        self.discontinuous_discrete_output = False
        self.tags = self._load_tags(tag_filepath)
        self.addresses = self._calculate_addresses(self.tags)
        self.map = {data['address']['start']: tag for tag, data in self.tags.items()}

    async def get(self) -> dict:
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

    def get_tags(self) -> dict:
        """Return all tags and associated configuration information.

        Use this data for debugging or to provide more detailed
        information on user interfaces.

        Returns:
            A dictionary containing information associated with each tag name.

        """
        return self.tags

    async def set(self, data_dict: Optional[dict] = None, *args, **kwargs
                  ) -> List[str]:
        """Set tag names to values.

        This function expects a dictionary of values or keyword arguments.
        See the following examples.

        >>> set({'av1': False, 'av2': False})
        >>> set(av1=False, av2=False)
        >>> set(target=0, setpoint=1.1)

        Returns:
            A list of write responses

        """
        discrete_to_write, registers_to_write = await self._parse_set_args(data_dict,
                                                                           args, kwargs)

        responses: List[str] = []
        if discrete_to_write:
            discrete_resp = await self._write_discrete_values(discrete_to_write)
            if any(r.isError() for r in discrete_resp):
                raise RuntimeError(f"Setting discrete values failed: {discrete_resp!s}")
            responses.extend(str(r) for r in discrete_resp)

        if registers_to_write:
            for key, value in registers_to_write.items():
                register_resp = await self._write_register_value(key, value)
                if register_resp.isError():
                    raise RuntimeError(f"Setting {key} failed: {register_resp!s}")
                responses.append(str(register_resp))
        return responses

    async def _parse_set_args(self, data_dict: Optional[dict],
                              args: tuple, kwargs: dict) -> Tuple[dict, dict]:
        """Parse and validate input to the set function."""
        if isinstance(data_dict, dict):
            kwargs.update(data_dict)
        if args or (data_dict and not isinstance(data_dict, dict)):
            raise TypeError(f"Invalid input. See the following docstring:\n"
                            f"{self.set.__doc__}")
        if not kwargs:
            raise TypeError(f"No settings provided. See the following docstring:\n"
                            f"{self.set.__doc__}")
        to_write = dict(kwargs.items())
        unsupported = set(to_write) - set(self.tags)
        if unsupported:
            raise ValueError(f"The tags file is missing the following tags:"
                             f" {', '.join(unsupported)}")
        discrete_to_write, registers_to_write = {}, {}
        for key, value in to_write.items():
            start_address = self.tags[key]['address']['start']
            data_type = self.tags[key]['type'].rstrip(digits)
            if type(value) == int and data_type == 'float':  # noqa: E721
                value = float(value)
            if type(value) != pydoc.locate(data_type):
                raise ValueError(f"Expected {key} to be a {data_type}.")
            if 0 <= start_address < 65536:
                discrete_to_write[key] = value
            elif 400000 <= start_address < 465536:
                registers_to_write[key] = value
            else:
                ValueError(f"{key} is not at a writeable address: {start_address}")
        return discrete_to_write, registers_to_write

    async def _write_register_value(self, key: str,
                                    value: Union[str, float, int]
                                    ) -> WriteMultipleRegistersResponse:
        """Write a single value to the holding registers.

        Currently registers are written one at a time to avoid issues with
        discontinuous modbus addresses.

        """
        start_address = self.tags[key]['address']['start'] - 400001
        bigendian = Endian.BIG if self.pymodbus35plus else Endian.Big  # type:ignore[attr-defined]
        lilendian = Endian.LITTLE if self.pymodbus35plus else Endian.Little  # type:ignore
        builder = BinaryPayloadBuilder(byteorder=bigendian,
                                       wordorder=lilendian)
        data_type = self.tags[key]['type']
        if data_type == 'float':
            builder.add_32bit_float(float(value))
        elif data_type == 'str' and isinstance(value, str):
            chars = self.tags[key]['length']
            if len(value) > chars:
                raise ValueError(f'{value} is too long for {key}. '
                                 f'Max: {chars} chars')
            builder.add_string(value.ljust(chars))
        elif data_type == 'int16':
            builder.add_16bit_int(int(value))
        elif data_type == 'int32':
            builder.add_32bit_int(int(value))
        else:
            raise ValueError("Missing data type.")
        resp = await self.write_registers(start_address,
                                          builder.build(),
                                          skip_encode=True)
        return resp[0]

    async def _write_discrete_values(self, discrete_to_write: dict
                                     ) -> List[Union[WriteSingleCoilResponse,
                                                     WriteMultipleCoilsResponse]]:
        """Write a dict of discrete values to the PLC.

        To reduce the number of requests, the complete current state is
        read then updated and written back.

        """
        if len(discrete_to_write) == 1 or self.discontinuous_discrete_output:
            return [await self.write_coil(self.tags[key]['address']['start'] - 1, val)
                    for key, val in discrete_to_write.items()]

        current_state = await self._read_discrete(self.addresses['discrete_output'])
        new_state = {**current_state, **discrete_to_write}
        vals = [new_state[key] for key in self.tags if key in new_state]
        assert len(vals) == len(new_state)
        return [await self.write_coils(
            self.addresses['discrete_output']['address'], vals)]

    async def _read_discrete(self, addresses: dict, output=True) -> dict:
        """Handle reading discrete values from the PLC."""
        result = {}
        if output:
            response = await self.read_coils(**addresses)
            current = addresses['address'] + 1
        else:
            response = await self.read_discrete_inputs(**addresses)
            current = addresses['address'] + 100001

        end = current + addresses['count']
        if isinstance(response, ExceptionResponse):
            func = response.function_code
            if (output and func != 129) or (output is False and func != 130):
                raise ValueError(f"Received function code {func} which does not match request")
            excep = response.exception_code
            read_type = "coil(s)" if output else "discrete input(s)"
            logging.error(f"Received MODBUS exception code {excep} when reading "
                          f"{addresses['count']} {read_type} at {addresses['address']}")
            return {}
        for bit in response.bits:
            if current > end:
                break
            elif current in self.map:
                result[self.map[current]] = bit
            current += 1
        return result

    async def _read_registers(self, a_type: str) -> dict:
        """Handle reading input or holding registers from the PLC."""
        r = await self.read_registers(**self.addresses[a_type], type=a_type)
        bigendian = Endian.BIG if self.pymodbus35plus else Endian.Big  # type:ignore[attr-defined]
        lilendian = Endian.LITTLE if self.pymodbus35plus else Endian.Little  # type:ignore
        decoder = BinaryPayloadDecoder.fromRegisters(r,
                                                     byteorder=bigendian,
                                                     wordorder=lilendian)
        current = self.addresses[a_type]['address'] + TYPE_START[a_type] + 1
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
                    try:
                        codec = 'unicode-escape'
                        test_decoder = deepcopy(decoder)
                        test_decoder.decode_string(chars).decode(codec)
                        result[tag] = decoder.decode_string(chars).decode(codec).strip('\u0000')
                    except UnicodeDecodeError as e:
                        result[tag] = decoder.decode_string(chars).decode(codec, 'ignore') \
                            .strip('\u0000')
                        logging.error(f"Decoding register {current} had an error,"
                                      f" which was ignored: {e}")
                    # Handle odd length strings
                    current += ceil(chars / 2)
                    decoder._pointer += chars % 2
                elif data_type == 'int16':
                    result[tag] = decoder.decode_16bit_int()
                    current += 1
                elif data_type == 'int32':
                    result[tag] = decoder.decode_32bit_int()
                    current += 2
                else:
                    raise ValueError("Missing data type.")
            else:
                # Empty modbus addresses could land you on a register that's not used
                decoder._pointer += 2
                current += 1
        return result

    @staticmethod
    def _load_tags(tag_filepath: str) -> dict:
        """Load tags from file path.

        This tag file is needed to identify the appropriate variable names,
        data types, and modbus addresses. I would love to be able to read
        this directly from the PLC but cannot find any documentation on the
        programming port (9999).

        """
        with open(tag_filepath) as csv_file:
            csv_data = csv_file.read().splitlines()
        csv_data[0] = csv_data[0].lstrip('## ')
        parsed: Dict[str, Dict[str, Any]] = {
            row['Tag Name']: {
                'address': {
                    'start': int(row['MODBUS Start Address']),
                    'end': int(row['MODBUS End Address'])
                },
                'id': row['System ID'],
                'comment': row['Comment'],
                'length': int(row['Number of Characters'] or 0),
                'type': DATA_TYPES.get(
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
        sorted_tags = {k: parsed[k] for k in
                       sorted(parsed, key=lambda k: parsed[k]['address']['start'])}
        return sorted_tags

    def _calculate_addresses(self, tags: dict) -> dict:
        """Determine the minimum number of requests to get all tags.

        Modbus limits request length to ~250 bytes (125 registers, 2000 coils).
        We could make this fun and automatic but I don't think most use cases
        need that level of fanciness. I'm leaving it very simple until someone
        tells me it's an issue.

        """
        addresses = sorted([tag['address']['start'] for tag in tags.values()]
                           + [tag['address']['end'] for tag in tags.values()])
        output: Dict[str, dict] = {}
        do_count = 0
        for a in addresses:
            if 0 < a < 65536:
                a_type = 'discrete_output'
                do_count += 1
            elif 100000 < a < 165536:
                a_type = 'discrete_input'
            elif 300000 < a < 365536:
                a_type = 'input'
            elif 400000 < a < 465536:
                a_type = 'holding'
            else:
                continue
            if a_type in output:
                output[a_type]['count'] = (a - TYPE_START[a_type]
                                           - output[a_type]['address'])
            else:
                output[a_type] = {'address': a - TYPE_START[a_type] - 1}

        for found_type in output:
            if output[found_type]['count'] > 2000:
                raise ValueError(f"Only supporting an address span of 2000 {found_type}."
                                 " If you need more, open a github issue at "
                                 "numat/productivity.")

        if 'discrete_output' in output and do_count / 2 < output['discrete_output']['count']:
            self.discontinuous_discrete_output = True
            logging.warning(
                "Warning: Your tags file has gaps in discrete output modbus addresses."
                " This driver will fall back to setting values in this range serially "
                "rather than as a block.")
        return output

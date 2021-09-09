"""Base functionality for modbus communication.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
import asyncio

try:
    from pymodbus.client.asynchronous.async_io import ReconnectingAsyncioModbusTcpClient
except ModuleNotFoundError:
    from pymodbus.client.asynchronous.asyncio import ReconnectingAsyncioModbusTcpClient
import pymodbus.exceptions

TYPE_START = {
    'discrete_output': 0,
    'discrete_input': 100000,
    'input': 300000,
    'holding': 400000,
}

DATA_TYPES = {
    'AIF32': 'float',  # Analog Input Float 32-bit
    'F32': 'float',    # Float 32-bit
    'AIS32': 'int32',  # Analog Input Signed integer 32-bit
    'AOS32': 'int32',  # Analog Output Signed integer 32-bit
    'S16': 'int16',    # Signed integer 16-bit
    'S32': 'int32',    # Signed integer 32-bit
    'C': 'bool',       # (C) Boolean
    'DI': 'bool',      # Discrete Input
    'DO': 'bool',      # Discrete Output
    'SBR': 'bool',     # System Boolean Read-only
    'SBRW': 'bool',    # System Boolean Read-Write
    'MST': 'bool',     # Module STatus bit
    'STR': 'str',      # STRing
    'SSTR': 'str',     # System STRing
    'SWR': 'int16',    # System Word Read-only
    'SWRW': 'int16'    # System Word Read-Write
}


class AsyncioModbusClient(object):
    """A generic asyncio client.

    This expands upon the pymodbus ReconnectionAsyncioModbusTcpClient by
    including standard timeouts, async context manager, and queued requests.
    """

    _register_types = ['holding', 'input']

    def __init__(self, address, timeout=1):
        """Set up communication parameters."""
        self.ip = address
        self.timeout = timeout
        self.client = ReconnectingAsyncioModbusTcpClient()
        asyncio.ensure_future(self._connect())
        self.open = False
        self.waiting = False

    async def __aenter__(self):
        """Asynchronously connect with the context manager."""
        await self._connect()
        return self

    async def __aexit__(self, *args):
        """Provide exit to the context manager."""
        self.close()

    async def _connect(self):
        """Start asynchronous reconnect loop."""
        self.waiting = True
        await self.client.start(self.ip)
        self.waiting = False
        if self.client.protocol is None:
            raise IOError(f"Could not connect to '{self.ip}'.")
        self.open = True

    async def read_coils(self, address, count):
        """Read modbus output coils (0 address prefix)."""
        return await self._request('read_coils', address, count)

    async def read_discrete_inputs(self, address, count):
        """Read modbus discrete inputs (1 address prefix)."""
        return await self._request('read_discrete_inputs', address, count)

    async def read_registers(self, address, count, type='holding', max_count=125):
        """Read modbus registers.

        The Modbus protocol doesn't allow responses longer than 250 bytes
        (ie. 125 registers, 62 DF addresses), which this function manages by
        chunking larger requests.
        """
        if max_count > 125:
            raise ValueError("Maximum of 125 registers can be read in one request.")
        if type not in self._register_types:
            raise ValueError(f"Register type {type} not in {self._register_types}.")
        registers = []
        while count > max_count:
            # if the last address read will be in the middle of a 32-bit tag
            # read one less address to avoid bad replies
            # https://github.com/numat/productivity/issues/38
            last_address = self.map.get(TYPE_START[type] + address + max_count, None)
            offset = -1 if (last_address
                            and self.tags[last_address]['type'] in ['int32', 'float']) else 0
            r = await self._request(f'read_{type}_registers', address, max_count + offset)
            address, count = address + (max_count + offset), count - (max_count + offset)
            registers += r.registers
        r = await self._request(f'read_{type}_registers', address, count)
        registers += r.registers
        return registers

    async def write_coil(self, address, value):
        """Write modbus coils."""
        return await self._request('write_coil', address, value)

    async def write_coils(self, address, values):
        """Write modbus coils."""
        return await self._request('write_coils', address, values)

    async def write_register(self, address, value, skip_encode=False):
        """Write a modbus register."""
        return await self._request('write_register', address, value, skip_encode=skip_encode)

    async def write_registers(self, address, values, skip_encode=False):
        """Write modbus registers.

        The Modbus protocol doesn't allow requests longer than 250 bytes
        (ie. 125 registers, 62 DF addresses), which this function manages by
        chunking larger requests.
        """
        responses = []
        while len(values) > 62:
            responses.append(await self._request(
                'write_registers', address, values, skip_encode=skip_encode))
            address, values = address + 124, values[62:]
        responses.append(await self._request(
            'write_registers', address, values, skip_encode=skip_encode))
        return responses

    async def _request(self, method, *args, **kwargs):
        """Send a request to the device and awaits a response.

        This mainly ensures that requests are sent serially, as the Modbus
        protocol does not allow simultaneous requests (it'll ignore any
        request sent while it's processing something). The driver handles this
        by assuming there is only one client instance. If other clients
        exist, other logic will have to be added to either prevent or manage
        race conditions.
        """
        while self.waiting:
            await asyncio.sleep(0.1)
        if self.client.protocol is None or not self.client.protocol.connected:
            raise TimeoutError("Not connected to device.")
        try:
            future = getattr(self.client.protocol, method)(*args, **kwargs)
        except AttributeError:
            raise TimeoutError("Not connected to device.")
        self.waiting = True
        try:
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError as e:
            if self.open:
                # This came from reading through the pymodbus@python3 source
                # Problem was that the driver was not detecting disconnect
                if hasattr(self, 'modbus'):
                    self.client.protocol_lost_connection(self.modbus)
                self.open = False
            raise TimeoutError(e)
        except pymodbus.exceptions.ConnectionException as e:
            raise ConnectionError(e)
        finally:
            self.waiting = False

    def close(self):
        """Close the TCP connection."""
        self.client.stop()
        self.open = False
        self.waiting = False

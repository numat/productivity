Productivity
============

##### NOTE: This is in very early stages of development.

Python ≥3.5 driver and command-line tool for [AutomationDirect Productivity Series PLCs](https://www.automationdirect.com/adc/overview/catalog/programmable_controllers/productivity_series_controllers).

<p align="center">
  <img src="https://www.automationdirect.com/images/overviews/p-series-cpus_400.jpg" />
</p>

Installation
============

```
pip install productivity
```

Usage
=====

### PLC Configuration

This driver uses Modbus TCP/IP for communication. Unlike the ClickPLC, modbus
addresses need to be manually configured in the Productivity PLC firmware (see
[manual](https://cdn.automationdirect.com/static/manuals/p2userm/p2userm.pdf)).

To use this driver, go to `Write Program → Tag Database`, scroll down to the values
you care about, and double click the `Mod Start` cell of each value to assign an address.
Then, go to `File → Export → Tags` to export a csv file. The file is used here so
you don't need to remember the addresses.

### Command Line

```
$ productivity the-plc-ip-address path/to/tags.csv
```

See `productivity --help` for more.

### Python

This driver uses Python ≥3.5's async/await syntax to asynchronously communicate with
a ClickPLC. For example:

```python
import asyncio
from productivity import ProductivityPLC

async def get():
    async with ProductivityPLC('the-plc-ip-address', 'path/to/tags.csv') as plc:
        print(await plc.get())

asyncio.run(get())
```

It's possible to set coils and registers on the PLC as well using keyword arguments
```python
async def set(**kwargs):
    async with ProductivityPLC('the-plc-ip-address', 'path/to/tags.csv') as plc:
        print(await plc.set(**kwargs))

asyncio.run(set(target=0, setpoint=1.1))
```
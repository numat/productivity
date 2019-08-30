Productivity
============

##### August 2019: This driver is in very early stages of development.

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
addresses need to be manually configured in the Productivity PLC firmware.

To do this, go to `Write Program → Tag Database`, scroll down to the values you
care about, and double click the `Mod Start` cell of each value. This will assign
Modbus addresses (e.g. `300001`) to the values.

Then, go to `File → Export → Tags` to export a csv file. This will be used
by this driver so you don't need to remember addresses.

More can be found in [the manual](https://cdn.automationdirect.com/static/manuals/p2userm/p2userm.pdf).

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

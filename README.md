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
addresses need to be manually configured in the PLC firmware.

To do this, go to `Write Program → Tag Database`, scroll down to the values you
care about, and click the `Mod Start` cell of each value. This will assign
Modbus addresses (e.g. `300001`) to the values.

More can be found in [the manual](https://cdn.automationdirect.com/static/manuals/p2userm/p2userm.pdf).

### Command Line

```
$ productivity the-plc-ip-address
```

This will print a sample of Modbus registers which can be piped as needed.
However, you'll likely want the python functionality below.

### Python

This uses Python ≥3.5's async/await syntax to asynchronously communicate with
a ClickPLC. For example:

```python
import asyncio
from productivity import ProductivityPLC

async def get():
    async with ProductivityPLC('the-plc-ip-address') as plc:
        print(await plc.get_inputs())

asyncio.run(get())
```

Currently, only reading float32 input registers is supported. I plan on building
this out as more functionality is required.

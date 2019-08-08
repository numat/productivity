"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
from productivity.driver import ProductivityPLC


def command_line():
    """Command-line tool for Productivity PLC communication."""
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Control a Productivity PLC "
                                     "from the command line.")
    parser.add_argument('address', help="The IP address of the PLC.")
    args = parser.parse_args()

    async def get():
        async with ProductivityPLC(args.address) as plc:
            d = await plc.get_inputs(list(range(100)))
            print(json.dumps(d, indent=4))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(get())
    loop.close()


if __name__ == '__main__':
    command_line()

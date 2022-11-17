"""
Python driver for AutomationDirect Productivity Series PLCs.

Distributed under the GNU General Public License v2
Copyright (C) 2019 NuMat Technologies
"""
from productivity.driver import ProductivityPLC


def command_line(args=None):
    """Command-line tool for Productivity PLC communication."""
    import argparse
    import asyncio
    import json

    import yaml

    parser = argparse.ArgumentParser(description="Control a Productivity PLC "
                                     "from the command line.")
    parser.add_argument('address', help="The IP address of the PLC.")
    parser.add_argument('tags', help="The PLC tag database file.")
    parser.add_argument('-s', '--set', type=yaml.safe_load,
                        help="Pass a YAML string with parameters to be set.")
    args = parser.parse_args(args)

    async def run():
        async with ProductivityPLC(args.address, args.tags) as plc:
            if args.set:
                await plc.set(**args.set)
            d = await plc.get()
            print(json.dumps(d, indent=4))

    loop = asyncio.new_event_loop()
    loop.run_until_complete(run())
    loop.close()


if __name__ == '__main__':
    command_line()

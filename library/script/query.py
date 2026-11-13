#!/usr/bin/env python3

"""Query an AlphaESS VitaPower and print every value."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    add_connection_args,
    connect_from_args,
    print_component,
)

from alphaess_modbus_vitapower import DEFAULT_UNIT_ID, VitaPower

# Modbus TCP over the LAN port is the only link the VitaPower serves.
CONNECTIONS = (("tcp", None),)

# The most registers one Modbus read may ask for.
MAX_COUNT = 125

RegisterRead = tuple[int, int, list[int] | str]

EXAMPLES = """examples:
  # the battery's LAN port (502 and unit 85 are the defaults)
  uv run script/query.py 192.168.1.28
  # every register read, plus ranges the library does not model
  uv run script/query.py 192.168.1.28 --raw --registers 0x0441:9 --registers 0x0889
"""


def _register_range(text: str) -> tuple[int, int]:
    """Parse ``ADDR[:COUNT]``, each decimal or 0x-prefixed."""
    address, _, count = text.partition(":")
    try:
        start, length = int(address, 0), int(count or "1", 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not ADDR[:COUNT]") from None
    if not 1 <= length <= MAX_COUNT or not 0 <= start <= 0x10000 - length:
        raise argparse.ArgumentTypeError(
            f"{text!r} must read 1 to {MAX_COUNT} registers ending by 0xFFFF"
        )
    return start, length


def _error(err: ModbusError) -> str:
    # A timeout arrives with no message of its own.
    return str(err) or type(err).__name__


def _line(label: str, value: object) -> None:
    print(f"{label:<16}{value}")


async def _read_registers(
    vitapower: VitaPower, ranges: list[tuple[int, int]]
) -> list[RegisterRead]:
    """Each holding range's values, or why it could not be read."""
    reads: list[RegisterRead] = []
    for start, count in ranges:
        try:
            values: (
                list[int] | str
            ) = await vitapower.modbus_unit.read_holding_registers(start, count)
        except ModbusError as err:
            values = _error(err)
        reads.append((start, count, values))
    return reads


def _print_registers(reads: list[RegisterRead]) -> None:
    for start, count, values in reads:
        print(f"\nRegisters 0x{start:04X}-0x{start + count - 1:04X}")
        if isinstance(values, str):
            print(f"  {values}")
            continue
        for offset, value in enumerate(values):
            print(f"  0x{start + offset:04X}  0x{value:04X}  {value}")


async def main() -> int:
    """Read one VitaPower and print it."""
    # Silence the backend's connect traceback; one line below says it.
    logging.getLogger().addHandler(logging.NullHandler())

    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_connection_args(parser, connections=CONNECTIONS)
    parser.add_argument(
        "--unit", type=int, default=DEFAULT_UNIT_ID, help="Modbus unit id"
    )
    parser.add_argument(
        "--raw", action="store_true", help="also dump every register read, as JSON"
    )
    parser.add_argument(
        "--registers",
        type=_register_range,
        action="append",
        default=[],
        metavar="ADDR[:COUNT]",
        help=f"also read these holding registers, up to {MAX_COUNT} at a time",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print the library's log",
    )
    args = parser.parse_args()
    if args.debug:
        library_log = logging.getLogger("alphaess_modbus_vitapower")
        library_log.setLevel(logging.DEBUG)
        library_log.addHandler(logging.StreamHandler())

    try:
        connection = await connect_from_args(args)
    except ModbusError as err:
        print(f"Could not connect to {args.target}: {_error(err)}")
        print("The VitaPower accepts one Modbus client: is another one connected?")
        return 1

    try:
        vitapower = await VitaPower.async_detect(connection.for_unit(args.unit))
        report = await vitapower.async_update()
        registers = await _read_registers(vitapower, args.registers)
        raw = await vitapower.async_read_raw() if args.raw else None
    except ModbusError as err:
        print(f"Could not read the VitaPower: {_error(err)}")
        return 1
    finally:
        await connection.close()

    _line("Serial number", vitapower.serial_number)
    _line("EMS version", vitapower.identity.ems_version)
    _line("Efficiency", vitapower.efficiency)
    for name in (
        "identity",
        *vitapower.readings_components,
        *vitapower.settings_components,
    ):
        print()
        print_component(getattr(vitapower, name), title=name)
    if report.failed:
        print("\nFailed to read:")
        for name, error in report.failed.items():
            print(f"  {name}: {_error(error)}")
    _print_registers(registers)
    if raw is not None:
        print("\nRaw registers")
        # The dump arrives address-ordered; sorting keys would undo that.
        print(json.dumps(raw, indent=2))
    return 0


raise SystemExit(asyncio.run(main()))

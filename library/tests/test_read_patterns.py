"""How many requests a poll costs, and which registers it never touches."""

from __future__ import annotations

from modbus_connection.mock import MockModbusUnit, ReadEvent

from alphaess_modbus_vitapower import VitaPower


def reads(unit: MockModbusUnit) -> list[tuple[int, int]]:
    """The reads since the last call, as (address, count)."""
    taken = [(event.address, event.count) for event in unit.read_events]
    unit.read_events.clear()
    return taken


async def test_first_readings_poll_reads_identity_once(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_update_readings()

    assert reads(unit) == [
        (0x0640, 10),  # firmware
        (0x0743, 14),  # serial number and EMS version
        (0x0100, 46),  # battery
        (0x0400, 65),  # inverter
        (0x0880, 9),  # dispatch
        (0x08D4, 2),  # system fault
    ]

    await vitapower.async_update_readings()
    assert reads(unit) == [(0x0100, 46), (0x0400, 65), (0x0880, 9), (0x08D4, 2)]


async def test_settings_poll(unit: MockModbusUnit, vitapower: VitaPower) -> None:
    await vitapower.async_update_readings()
    reads(unit)

    await vitapower.async_update_settings()

    assert reads(unit) == [(0x0800, 1), (0x0850, 6)]


async def test_never_reads_unstable_or_network_registers(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_update()
    await vitapower.async_read_raw()

    touched = {
        address
        for event in unit.read_events
        if isinstance(event, ReadEvent)
        for address in range(event.address, event.address + event.count)
    }
    assert not touched & set(range(0x0441, 0x044A))  # layout shifts
    assert not touched & set(range(0x0808, 0x0811))  # network settings
    assert not touched & {0x0453, 0x0454, *range(0x072C, 0x0740)}  # refused

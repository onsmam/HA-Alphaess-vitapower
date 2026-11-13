"""What a poll does when the battery refuses, stalls or drops the link."""

from __future__ import annotations

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit

from alphaess_modbus_vitapower import VitaPower


async def test_refused_component_keeps_the_rest(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    unit.fail_read(0x0880, IllegalDataAddressError())

    report = await vitapower.async_update_readings()

    assert report.updated == {"battery", "inverter", "system"}
    assert isinstance(report.failed["dispatch"], IllegalDataAddressError)
    assert vitapower.dispatch.power is None
    assert vitapower.inverter.ac_power == 797


async def test_failed_component_keeps_previous_values(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_update_readings()
    unit.fail_read(0x0400, IllegalDataAddressError())
    unit.holding[0x040C] = [0, 500]

    report = await vitapower.async_update_readings()

    assert "inverter" in report.failed
    assert vitapower.inverter.ac_power == 797


async def test_dead_link_raises(unit: MockModbusUnit, vitapower: VitaPower) -> None:
    await vitapower.async_update_readings()
    unit.fail_requests(ModbusConnectionError("gone"))

    with pytest.raises(ModbusConnectionError):
        await vitapower.async_update_readings()


async def test_silent_battery_raises_on_the_first_timeout(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_update_readings()
    unit.fail_requests(ModbusTimeoutError())

    with pytest.raises(ModbusTimeoutError):
        await vitapower.async_update_readings()
    assert len(unit.read_events) == 7  # setup's two, then the battery block


async def test_identity_retried_after_a_failed_setup(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    unit.fail_read(0x0640, IllegalDataAddressError())

    report = await vitapower.async_update_readings()

    assert report.complete
    assert vitapower.identity.firmware_inverter is None

    unit.fail_read(0x0640, None)
    await vitapower.async_update_readings()

    assert vitapower.identity.firmware_inverter == "V3.05.011"

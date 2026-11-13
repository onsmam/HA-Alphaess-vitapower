"""Decoded values, checked against real VitaPower scans."""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit

from alphaess_modbus_vitapower import NotAVitaPowerError, VitaPower
from alphaess_modbus_vitapower.identity import Identity

from .conftest import CHARGING, CHARGING_500W, SERIAL, seed


async def test_discharging_under_cloud_dispatch(vitapower: VitaPower) -> None:
    report = await vitapower.async_update()

    assert report.complete
    battery = vitapower.battery
    assert battery.soc == 30.4
    assert battery.voltage == 38.7
    assert battery.current == 23.2
    assert battery.dc_power == 857
    assert battery.min_cell_voltage == 3.225
    assert (battery.min_cell_voltage_pack, battery.min_cell_voltage_cell) == (2, 1)
    assert battery.max_cell_voltage == 3.234
    assert battery.min_cell_temperature == 14.0
    assert battery.max_cell_temperature == 16.0
    assert battery.max_charge_current == 61.8
    assert battery.max_discharge_current == 156.7
    assert battery.max_charge_power == 2399
    assert battery.max_discharge_power == 6075
    assert battery.capacity == 12.0
    assert battery.module_count == 3
    assert battery.bms_version == 102
    assert battery.soh == 100.0
    assert battery.warning == 0
    assert battery.fault == 0
    assert battery.energy_charged == 0
    assert battery.energy_discharged == 0.9
    assert battery.energy_charged_from_grid == 0

    inverter = vitapower.inverter
    assert inverter.ac_power == 797
    assert inverter.grid_voltage == 238.0
    assert inverter.ac_current == 3.3
    assert inverter.grid_frequency == 49.98
    assert inverter.temperature == 27.0
    assert inverter.fault == 0
    assert vitapower.system.fault == 0

    dispatch = vitapower.dispatch
    assert dispatch.active is True
    assert dispatch.power == 798
    # Written as 0, not 32000: the quirk reads as unknown, not -32000 var.
    assert dispatch.reactive_power is None
    assert dispatch.mode == 2
    assert dispatch.soc_target == 10.0
    assert dispatch.duration == 180

    settings = vitapower.settings
    assert settings.discharge_cutoff_soc == 10
    assert settings.charge_cutoff_soc == 100
    assert settings.max_feed_in == 100

    assert vitapower.efficiency == 93.0


async def test_identity(vitapower: VitaPower) -> None:
    await vitapower.async_update_readings()

    identity = vitapower.identity
    assert identity.serial_number == SERIAL
    assert identity.firmware_inverter == "V3.05.011"
    assert identity.firmware_arm == "V2.01.003"
    assert identity.ems_version == "1.1.24-CFU"


async def test_charging_full_power(unit: MockModbusUnit) -> None:
    seed(unit, CHARGING)
    vitapower = VitaPower(unit, serial_number=SERIAL)
    await vitapower.async_update()

    assert vitapower.inverter.ac_power == -3679
    assert vitapower.battery.dc_power == -3402
    assert vitapower.battery.current == -82.1
    # The BMS raises the charge limit while charging.
    assert vitapower.battery.max_charge_current == 156.9
    assert vitapower.battery.max_charge_power == 6264
    assert vitapower.dispatch.active is False
    # A stopped dispatch is 32000: 0 W, not unknown.
    assert vitapower.dispatch.power == 0
    assert vitapower.dispatch.reactive_power == 0
    assert vitapower.dispatch.duration == 90
    assert vitapower.efficiency == 92.5


async def test_charging_500w(unit: MockModbusUnit) -> None:
    seed(unit, CHARGING_500W)
    vitapower = VitaPower(unit, serial_number=SERIAL)
    await vitapower.async_update_readings()

    assert vitapower.inverter.ac_power == -499
    assert vitapower.battery.dc_power == -446
    assert vitapower.efficiency == 89.4


@pytest.mark.parametrize(
    ("ac", "dc", "expected"),
    [
        (0x0000_031D, 857, 93.0),  # 797 W out of 857 W
        (50, 60, None),  # standby
        (500, 0xFE0C, None),  # -500 W: the sides disagree for a moment
    ],
)
async def test_efficiency(
    unit: MockModbusUnit, ac: int, dc: int, expected: float | None
) -> None:
    unit.holding[0x040C] = [ac >> 16, ac & 0xFFFF]
    unit.holding[0x0126] = dc
    vitapower = VitaPower(unit, serial_number=SERIAL)
    await vitapower.async_update_readings()

    assert vitapower.efficiency == expected


def test_efficiency_before_a_poll(vitapower: VitaPower) -> None:
    assert vitapower.efficiency is None


async def test_detect(unit: MockModbusUnit) -> None:
    vitapower = await VitaPower.async_detect(unit)

    assert vitapower.serial_number == SERIAL
    assert vitapower.identity.firmware_inverter == "V3.05.011"


async def test_detect_without_serial(unit: MockModbusUnit) -> None:
    address = Identity.serial_number.address
    unit.holding[address] = [0] * Identity.serial_number.count

    with pytest.raises(NotAVitaPowerError):
        await VitaPower.async_detect(unit)


async def test_link_settings(unit: MockModbusUnit) -> None:
    VitaPower(unit, serial_number=SERIAL)

    assert unit.required_connect_delay == 1.0
    assert unit.message_spacing == 0.03


async def test_read_raw_redacts_serial(vitapower: VitaPower) -> None:
    raw = await vitapower.async_read_raw(redact_serial=True)

    holding = raw["holding"]
    assert 0x0743 not in holding
    assert 0x074A not in holding
    assert holding[0x0102] == 304
    assert 0x074B in holding  # the EMS version stays

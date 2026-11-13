"""The register map, checked against real VitaPower scans."""

import pytest

from custom_components.alphaess_vitapower.registers import (
    BLOCKS,
    EXCLUDED_RANGES,
    FIELDS,
    decode_all,
    decode_string,
    efficiency,
)

from .scans import CHARGE_500W, CHARGE_3680W, DISCHARGE_800W, load_scan


def test_blocks_skip_excluded_ranges() -> None:
    """No block touches an address that fails or shifts."""
    for block in BLOCKS:
        for excluded in EXCLUDED_RANGES:
            assert not set(block.addresses) & set(excluded), block.key


def test_blocks_are_readable_in_every_full_scan() -> None:
    """Every address a block reads answered in the full scans."""
    for name in (DISCHARGE_800W, CHARGE_3680W):
        registers = load_scan(name)
        for block in BLOCKS:
            missing = [a for a in block.addresses if a not in registers]
            assert not missing, (name, block.key, [hex(a) for a in missing])


def test_discharging_800w_cloud_dispatch() -> None:
    """18:12 scan: the cloud dispatches 798 W, the battery delivers 797 W."""
    data = decode_all(load_scan(DISCHARGE_800W))
    assert data["soc"] == 30.4
    assert data["ac_power"] == 797
    assert data["dc_power"] == 857
    assert data["battery_voltage"] == 38.7
    assert data["battery_current"] == 23.2
    assert data["energy_charged"] == 0
    assert data["energy_discharged"] == 0.9
    assert data["energy_charged_grid"] == 0
    assert data["grid_voltage"] == 238.0
    assert data["ac_current"] == 3.3
    assert data["grid_frequency"] == 49.98
    assert data["inverter_temperature"] == 27.0
    assert data["cell_voltage_min"] == 3.225
    assert data["cell_voltage_max"] == 3.234
    assert data["cell_temperature_min"] == 14.0
    assert data["cell_temperature_max"] == 16.0
    assert data["max_charge_power"] == 2399
    assert data["max_discharge_power"] == 6075
    assert data["max_charge_current"] == 61.8
    assert data["max_discharge_current"] == 156.7
    assert data["soh"] == 100.0
    assert data["capacity"] == 12.0
    assert data["module_count"] == 3
    assert data["bms_version"] == 102
    assert data["battery_warning"] == 0
    assert data["battery_fault"] == 0
    assert data["inverter_fault"] == 0
    assert data["system_fault"] == 0
    assert data["discharge_cutoff_soc"] == 10
    assert data["charge_cutoff_soc"] == 100
    assert data["max_feed_in"] == 100
    assert data["dispatch_active"] is True
    assert data["dispatch_power"] == 798
    assert data["dispatch_mode"] == 2
    assert data["dispatch_soc"] == 10.0
    assert data["dispatch_duration"] == 180
    assert data["efficiency"] == 93.0
    assert data["firmware_inverter"] == "V3.05.011"
    assert data["firmware_arm"] == "V2.01.003"
    assert data["ems_version"] == "1.1.24-CFU"
    assert data["serial_number"] == "ALG0REDACTED001"


def test_charging_3680w() -> None:
    """18:20 scan: charging at full power from the app, no dispatch."""
    data = decode_all(load_scan(CHARGE_3680W))
    assert data["ac_power"] == -3679
    assert data["dc_power"] == -3402
    assert data["battery_current"] == -82.1
    assert data["soc"] == 29.6
    assert data["energy_discharged"] == 1.0
    # The BMS raises the charge limit while charging.
    assert data["max_charge_current"] == 156.9
    assert data["max_charge_power"] == 6264
    assert data["dispatch_active"] is False
    # Stopped dispatch: 32000 offset = 0 W, SOC target 0.
    assert data["dispatch_power"] == 0
    assert data["dispatch_soc"] == 0
    assert data["dispatch_duration"] == 90
    assert data["efficiency"] == 92.5


def test_charging_500w() -> None:
    """Charging at 500 W: efficiency DC/AC."""
    data = decode_all(load_scan(CHARGE_500W))
    assert data["ac_power"] == -499
    assert data["dc_power"] == -446
    assert data["battery_current"] == -11.6
    assert data["efficiency"] == 89.4
    # This scan did not cover the firmware block.
    assert data["firmware_inverter"] is None


def test_missing_registers_decode_as_unknown() -> None:
    """Nothing read yet: every field is None, nothing raises."""
    data = decode_all({})
    assert all(data[field.key] is None for field in FIELDS)
    assert data["efficiency"] is None
    assert data["dispatch_active"] is None
    assert data["ems_version"] is None


def test_dispatch_power_quirk() -> None:
    """Both dispatch power words 0 is "not set", not -32000 W."""
    data = decode_all({0x0881: 0, 0x0882: 0})
    assert data["dispatch_power"] is None


@pytest.mark.parametrize(
    ("ac", "dc", "expected"),
    [
        (797, 857, 93.0),
        (-3682, -3405, 92.5),
        (50, 60, None),  # below 100 W
        (500, None, None),
        (500, -500, None),  # opposite signs: transient
    ],
)
def test_efficiency(ac: int, dc: int | None, expected: float | None) -> None:
    """Discharging AC/DC, charging DC/AC."""
    assert efficiency(ac, dc) == expected


def test_decode_string() -> None:
    """High byte first, NUL padding dropped."""
    assert decode_string([0x5633, 0x2E30, 0x352E, 0x3031, 0x3100]) == "V3.05.011"

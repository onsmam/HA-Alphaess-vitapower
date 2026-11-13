"""The battery, the 0x0100 register block."""

from __future__ import annotations

from modbus_connection.model import gauge, integer, uint32

from .model import VitaPowerComponent


class Battery(VitaPowerComponent):
    """State of charge, cells, BMS limits and the battery's energy counters.

    One block from 0x0100 to 0x012D, read in a single request. Current and
    power are positive while discharging and negative while charging.
    """

    voltage = gauge(0x0100, 0.1, signed=False, unit="V")
    current = gauge(0x0101, 0.1, signed=True, unit="A")
    """Negative while charging."""
    soc = gauge(0x0102, 0.1, signed=False, unit="%")
    status = integer(0x0103, signed=False)
    """Undocumented; 257 in every scan so far."""
    relay_status = integer(0x0104, signed=False)
    """Undocumented; 3 in every scan so far."""

    min_cell_voltage_pack = integer(0x0105, signed=False)
    min_cell_voltage_cell = integer(0x0106, signed=False)
    min_cell_voltage = gauge(0x0107, 0.001, signed=False, unit="V")
    max_cell_voltage_pack = integer(0x0108, signed=False)
    max_cell_voltage_cell = integer(0x0109, signed=False)
    max_cell_voltage = gauge(0x010A, 0.001, signed=False, unit="V")
    min_cell_temperature_pack = integer(0x010B, signed=False)
    min_cell_temperature_cell = integer(0x010C, signed=False)
    min_cell_temperature = gauge(0x010D, 0.1, signed=True, unit="°C")
    max_cell_temperature_pack = integer(0x010E, signed=False)
    max_cell_temperature_cell = integer(0x010F, signed=False)
    max_cell_temperature = gauge(0x0110, 0.1, signed=True, unit="°C")

    max_charge_current = gauge(0x0111, 0.1, signed=False, unit="A")
    """Set by the BMS, and raised while charging (61.9 A idle, 156.9 A charging)."""
    max_discharge_current = gauge(0x0112, 0.1, signed=False, unit="A")
    max_charge_voltage = gauge(0x0113, 0.1, signed=False, unit="V")
    min_discharge_voltage = gauge(0x0114, 0.1, signed=False, unit="V")
    bms_version = integer(0x0115, signed=False)
    module_count = integer(0x0118, signed=False)
    capacity = gauge(0x0119, 0.1, signed=False, unit="kWh")
    soh = gauge(0x011B, 0.1, signed=False, unit="%")
    warning = uint32(0x011C)
    """Warning bitmask; the bits are undocumented, 0 is no warning."""
    fault = uint32(0x011E)
    """Fault bitmask; the bits are undocumented, 0 is no fault."""

    energy_charged = uint32(0x0120, scale=0.1, unit="kWh")
    """Updated in batches by the battery, minutes behind, not live."""
    energy_discharged = uint32(0x0122, scale=0.1, unit="kWh")
    energy_charged_from_grid = uint32(0x0124, scale=0.1, unit="kWh")
    dc_power = integer(0x0126, signed=True, unit="W")
    """Battery-side power; negative while charging."""

    max_charge_power = integer(0x012C, signed=False, unit="W")
    """The BMS charge limit: battery voltage times ``max_charge_current``."""
    max_discharge_power = integer(0x012D, signed=False, unit="W")
    """The BMS discharge limit: battery voltage times ``max_discharge_current``."""

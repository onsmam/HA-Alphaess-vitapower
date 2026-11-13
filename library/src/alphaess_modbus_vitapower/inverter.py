"""The inverter, the 0x0400 register block, and the system fault register."""

from __future__ import annotations

from modbus_connection.model import gauge, int32, integer, uint32

from .model import VitaPowerComponent


class Inverter(VitaPowerComponent):
    """AC output, grid frequency, temperature and the inverter's fault bitmask.

    The VitaPower is single phase: the L2 and L3 registers read 0 and are left
    out. ``ac_power`` is positive while discharging, negative while charging.
    """

    grid_voltage = gauge(0x0400, 0.1, signed=False, unit="V")
    ac_current = gauge(0x0403, 0.1, signed=False, unit="A")
    """Always positive, whichever way the power flows."""
    ac_power = int32(0x040C, unit="W")
    grid_frequency = gauge(0x041C, 0.01, signed=False, unit="Hz")
    temperature = gauge(0x0435, 0.1, signed=True, unit="°C")
    fault = uint32(0x043A)
    """Fault bitmask; the bits are undocumented, 0 is no fault."""
    work_mode = integer(0x0440, signed=False)
    """Undocumented; 1 in every scan so far."""


class System(VitaPowerComponent):
    """The system fault register."""

    fault = uint32(0x08D4)
    """Fault bitmask; the bits are undocumented, 0 is no fault."""

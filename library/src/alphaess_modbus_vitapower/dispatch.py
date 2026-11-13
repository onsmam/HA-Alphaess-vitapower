"""Remote dispatch, the 0x0880 register block."""

from __future__ import annotations

from modbus_connection.model import boolean, gauge, int32, integer, uint32

from .model import VitaPowerComponent

# Power is stored as P + 32000, so 32000 is 0 W.
DISPATCH_OFFSET = 32000


class Dispatch(VitaPowerComponent):
    """What the battery has been told to do over Modbus.

    The vendor's cloud writes this block itself, renewing it about every 180 s
    while it controls the battery; ``active`` tells whether a dispatch runs.
    Charging the battery from the vendor's app does not go through it.
    """

    active = boolean(0x0880)
    power = int32(0x0881, offset=-DISPATCH_OFFSET, nan=0, unit="W")
    """Positive discharges, negative charges.

    Both words 0 is not an offset value but "not set", so it reads as ``None``.
    """
    reactive_power = int32(0x0883, offset=-DISPATCH_OFFSET, nan=0, unit="var")
    """Written as 0, not 32000, while the cloud dispatches; that reads ``None``."""
    mode = integer(0x0885, signed=False)
    """2 while the cloud dispatches by state of charge, 0 when stopped."""
    soc_target = gauge(0x0886, 0.4, signed=False, unit="%")
    """In steps of 0.4 %: the cloud writes 25 for a 10 % cut-off."""
    duration = uint32(0x0887, unit="s")

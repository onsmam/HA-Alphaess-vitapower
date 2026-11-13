"""Configuration registers, the 0x0800 block."""

from __future__ import annotations

from modbus_connection.model import integer

from .model import VitaPowerComponent


class Settings(VitaPowerComponent):
    """The limits the battery has been configured with.

    Read-only for now: none of these has been written to a VitaPower yet.
    """

    max_feed_in = integer(0x0800, signed=False, unit="%")
    discharge_cutoff_soc = integer(0x0850, signed=False, unit="%")
    charge_cutoff_soc = integer(0x0855, signed=False, unit="%")

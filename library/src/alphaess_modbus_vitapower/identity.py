"""Serial number and firmware versions, the 0x0640 and 0x0740 blocks."""

from __future__ import annotations

from modbus_connection.model import integer, string

from .model import VitaPowerComponent


class Identity(VitaPowerComponent):
    """What the battery says it is.

    The serial number sits at 0x0743, mirrored at 0x0706. The ASCII string at
    0x064A, which other AlphaESS maps read as the serial, is something else on
    the VitaPower.
    """

    firmware_inverter = string(0x0640, 5)
    firmware_arm = string(0x0645, 5)
    serial_number = string(0x0743, 8)
    _ems_major = integer(0x074B, signed=False)
    _ems_minor = integer(0x074C, signed=False)
    _ems_patch = integer(0x074D, signed=False)
    _ems_suffix = string(0x074F, 2)

    @property
    def ems_version(self) -> str | None:
        """The EMS firmware, such as ``1.1.24-CFU``."""
        parts = (self._ems_major, self._ems_minor, self._ems_patch)
        if any(part is None for part in parts):
            return None
        version = ".".join(str(part) for part in parts)
        if suffix := self._ems_suffix:
            return f"{version}-{suffix}"
        return version

"""The top-level object for an AlphaESS VitaPower."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Final, Self

from modbus_connection import ModbusError
from modbus_connection.model import Device, Raw

from .battery import Battery
from .dispatch import Dispatch
from .identity import Identity
from .inverter import Inverter, System
from .model import UpdateReport
from .settings import Settings

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

# The unit id the VitaPower answers on.
DEFAULT_UNIT_ID: Final = 85

# Link settings a VitaPower has been running with over its LAN port: a pause
# after the link opens, and a quiet gap around each request.
CONNECT_DELAY: Final = 1.0
MESSAGE_SPACING: Final = 0.03

# Below this, on either side, the AC/DC ratio is mostly standby consumption.
EFFICIENCY_MIN_POWER: Final = 100

_IDENTITY_ATTEMPTS = 3

# Every component the readings poll reads.
READING_COMPONENTS: Final[tuple[str, ...]] = (
    "battery",
    "inverter",
    "dispatch",
    "system",
)
# Every component the settings poll reads.
SETTING_COMPONENTS: Final[tuple[str, ...]] = ("settings",)


class NotAVitaPowerError(ModbusError):
    """The device answered, but not with a VitaPower serial number."""


class VitaPower(Device):
    """An AlphaESS VitaPower reached through a ``ModbusUnit``.

    The VitaPower answers Modbus TCP on its LAN port only, and accepts one
    client at a time: share the unit rather than opening a second link.
    """

    def __init__(self, unit: ModbusUnit, *, serial_number: str) -> None:
        """Set up the sub-systems; nothing is read until the first poll."""
        super().__init__(unit)
        unit.require_connect_delay(CONNECT_DELAY)
        unit.set_message_spacing(MESSAGE_SPACING)
        self.serial_number = serial_number
        self.identity = Identity(unit)
        self.battery = Battery(unit)
        self.inverter = Inverter(unit)
        self.dispatch = Dispatch(unit)
        self.system = System(unit)
        self.settings = Settings(unit)
        self._setup_lock = asyncio.Lock()
        self._identity_pending = False

    @classmethod
    async def async_detect(cls, unit: ModbusUnit) -> Self:
        """Build a VitaPower for a caller that does not know its serial.

        Raises ``NotAVitaPowerError`` if the device reports no serial number.
        """
        identity = Identity(unit)
        await identity.async_update(notify=False)
        serial_number = identity.serial_number
        if not serial_number or not serial_number.isprintable():
            raise NotAVitaPowerError(
                f"no serial number at 0x{Identity.serial_number.address:04X}"
            )
        device = cls(unit, serial_number=serial_number)
        device.identity = identity
        return device

    @property
    def connected(self) -> bool:
        """Whether the link to the battery is open."""
        return self.modbus_unit.connected

    @property
    def readings_components(self) -> tuple[str, ...]:
        """The component names the readings poll reads."""
        return READING_COMPONENTS

    @property
    def settings_components(self) -> tuple[str, ...]:
        """The component names the settings poll reads."""
        return SETTING_COMPONENTS

    @property
    def efficiency(self) -> float | None:
        """AC/DC conversion efficiency in %, from the last readings poll.

        Discharging, AC out over DC in; charging, DC in over AC out. ``None``
        below ``EFFICIENCY_MIN_POWER`` on either side, and while the two sides
        disagree on the direction, which happens for a moment when it turns.
        """
        ac = self.inverter.ac_power
        dc = self.battery.dc_power
        if ac is None or dc is None:
            return None
        if abs(ac) < EFFICIENCY_MIN_POWER or abs(dc) < EFFICIENCY_MIN_POWER:
            return None
        if (ac > 0) != (dc > 0):
            return None
        ratio = ac / dc if ac > 0 else dc / ac
        return round(ratio * 100, 1)

    async def async_ensure_setup(self) -> None:
        """Run setup once, one caller at a time."""
        async with self._setup_lock:
            await super().async_ensure_setup()

    async def _async_setup(self) -> None:
        """Read the firmware versions, which never change."""
        if self.identity.firmware_inverter is None:
            await self.async_read_identity()

    async def async_read_identity(self) -> None:
        """Read the firmware versions, never failing over them.

        A failed read is tried again on each later poll that answers.
        """
        if (err := await self._async_try_identity(_IDENTITY_ATTEMPTS)) is not None:
            _LOGGER.warning(
                "VitaPower %s: could not read identity after %d tries: %s",
                self.serial_number,
                _IDENTITY_ATTEMPTS,
                err,
            )

    async def _async_try_identity(self, attempts: int) -> ModbusError | None:
        """Read the identity within ``attempts`` tries; the last error if not."""
        failure: ModbusError | None = None
        for _ in range(attempts):
            try:
                await self.identity.async_update()
            except ModbusError as err:
                failure = err
                _LOGGER.debug(
                    "VitaPower %s: could not read identity: %s",
                    self.serial_number,
                    err,
                )
            else:
                self._identity_pending = False
                return None
        self._identity_pending = True
        return failure

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the battery measures: power, charge, cells, faults."""
        report = await self.async_poll(READING_COMPONENTS)
        if self._identity_pending and report.updated:
            await self._async_try_identity(1)
        return report

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the configured limits, which only change when written."""
        return await self.async_poll(SETTING_COMPONENTS)

    async def async_update(self) -> UpdateReport:
        """Refresh readings and settings together in one report."""
        return await self.async_poll((*READING_COMPONENTS, *SETTING_COMPONENTS))

    async def async_read_raw(
        self, names: Iterable[str] | None = None, *, redact_serial: bool = False
    ) -> Raw:
        """Every register this device reads, undecoded, for diagnostics."""
        if names is None:
            names = ("identity", *READING_COMPONENTS, *SETTING_COMPONENTS)
        raw = await super().async_read_raw(names)
        if redact_serial and (holding := raw.get("holding")) is not None:
            serial = Identity.serial_number
            for address in range(serial.address, serial.address + serial.count):
                holding.pop(address, None)
        return raw

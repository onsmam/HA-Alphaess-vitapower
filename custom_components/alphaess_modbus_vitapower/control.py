"""Remote control of a VitaPower through its dispatch block."""

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from modbus_connection import ModbusError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DEFAULT_CHARGE_CUTOFF,
    DEFAULT_DISCHARGE_CUTOFF,
    DISPATCH_DURATION,
    DOMAIN,
    KEEPALIVE_INTERVAL,
    MODE_AUTO,
    MODE_OFF,
)
from .coordinator import VitaPowerConfigEntry, VitaPowerDataUpdateCoordinator
from .vendor.alphaess_modbus_vitapower import DispatchCommand, VitaPower

_LOGGER = logging.getLogger(__name__)


class VitaPowerController:
    """Turn a control mode and a power setpoint into dispatch commands.

    The setpoint follows DAO: positive charges the battery, negative
    discharges it. Every command lasts ``DISPATCH_DURATION`` seconds in the
    battery and is written again every ``KEEPALIVE_INTERVAL`` seconds, so the
    battery takes control back itself soon after Home Assistant stops.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VitaPowerConfigEntry,
        readings: VitaPowerDataUpdateCoordinator,
    ) -> None:
        """Initialize the controller; nothing is written yet."""
        self.hass = hass
        self.entry = entry
        self.readings = readings
        self.device: VitaPower = readings.device
        self.mode = MODE_AUTO
        self.setpoint = 0
        self._overridden = False
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_start(self) -> None:
        """Rewrite the command periodically and watch for overrides."""
        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_keepalive, timedelta(seconds=KEEPALIVE_INTERVAL)
            )
        )
        self.entry.async_on_unload(
            self.readings.async_add_listener(self._async_check_override)
        )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call ``listener`` whenever the mode or setpoint changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def command(self) -> DispatchCommand | None:
        """The command the mode and setpoint ask for; ``None`` for no command."""
        if self.mode == MODE_AUTO:
            return None
        if self.mode == MODE_OFF or self.setpoint == 0:
            soc = self.device.battery.soc
            return DispatchCommand(
                power=0,
                target_soc=DEFAULT_DISCHARGE_CUTOFF if soc is None else soc,
                duration=DISPATCH_DURATION,
            )
        settings = self.device.settings
        if self.setpoint > 0:
            target = settings.charge_cutoff_soc
            default = DEFAULT_CHARGE_CUTOFF
        else:
            target = settings.discharge_cutoff_soc
            default = DEFAULT_DISCHARGE_CUTOFF
        return DispatchCommand(
            # The library counts discharging as positive.
            power=-self.setpoint,
            target_soc=default if target is None else target,
            duration=DISPATCH_DURATION,
        )

    async def async_set_mode(self, mode: str) -> None:
        """Switch mode and write what it asks for now."""
        self.mode = mode
        self._notify()
        await self.async_apply()

    async def async_set_setpoint(self, setpoint: int) -> None:
        """Change the setpoint and write it now."""
        self.setpoint = setpoint
        self._notify()
        await self.async_apply()

    async def async_apply(self) -> None:
        """Write the current command, or stop one this controller wrote.

        Raises ``HomeAssistantError`` if the battery does not take the write.
        """
        command = self.command()
        try:
            if command is not None:
                await self.device.async_dispatch(command)
            elif self.device.dispatch_command is not None:
                await self.device.async_stop_dispatch()
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _async_keepalive(self, now: datetime) -> None:
        """Renew the command before the battery ends it."""
        if self.mode == MODE_AUTO:
            return
        try:
            await self.async_apply()
        except HomeAssistantError as err:
            _LOGGER.warning(
                "%s: could not renew the dispatch: %s", self.entry.title, err
            )

    @callback
    def _async_check_override(self) -> None:
        """Log once when something else, such as the vendor's cloud, took over."""
        overridden = self.device.dispatch_overridden
        if overridden and not self._overridden:
            _LOGGER.warning(
                "%s: another client replaced the dispatch command; "
                "it is written again every %s s",
                self.entry.title,
                KEEPALIVE_INTERVAL,
            )
        self._overridden = overridden

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

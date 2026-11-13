"""Data update coordinator for AlphaESS VitaPower batteries."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from alphaess_modbus_vitapower import UpdateReport, VitaPower
from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, DEFAULT_NAME, DOMAIN, MODEL

_LOGGER = logging.getLogger(__name__)


class VitaPowerDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll one half of a VitaPower: its readings or its settings."""

    config_entry: VitaPowerConfigEntry
    device: VitaPower

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VitaPowerConfigEntry,
        name: str,
        device: VitaPower,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._failing: set[str] = set()

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        info = dr.DeviceInfo(
            identifiers={(DOMAIN, self.device.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=MODEL,
            name=DEFAULT_NAME,
            serial_number=self.device.serial_number,
        )
        if ems_version := self.device.identity.ems_version:
            info["sw_version"] = ems_version
        return info

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        # The address can be handed to another battery after setup.
        serial = self.device.identity.serial_number
        if serial and serial != self.device.serial_number:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
            )
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        self._log_component_changes(report)
        return report

    def _log_component_changes(self, report: UpdateReport) -> None:
        """Log a component's first failure and its recovery, once each."""
        for name, cause in report.failed.items():
            if name not in self._failing:
                self._failing.add(name)
                _LOGGER.warning(
                    "%s: %s failed to refresh, its entities are unavailable: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated & self._failing:
            self._failing.discard(name)
            _LOGGER.info("%s: %s is available again", self.name, name)


@dataclass
class VitaPowerRuntimeData:
    """Class to hold runtime data."""

    readings: VitaPowerDataUpdateCoordinator
    settings: VitaPowerDataUpdateCoordinator

    def coordinator_for(self, component: str) -> VitaPowerDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.readings.device.readings_components:
            return self.readings
        return self.settings


type VitaPowerConfigEntry = ConfigEntry[VitaPowerRuntimeData]

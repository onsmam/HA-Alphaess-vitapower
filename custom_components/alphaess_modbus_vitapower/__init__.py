"""Integrate AlphaESS VitaPower batteries into Home Assistant."""

from datetime import timedelta

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID, SCAN_INTERVAL, SETTINGS_SCAN_INTERVAL
from .coordinator import (
    VitaPowerConfigEntry,
    VitaPowerDataUpdateCoordinator,
    VitaPowerRuntimeData,
)
from .vendor.alphaess_modbus_vitapower import VitaPower

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:
    """Set up a VitaPower from a config entry."""
    serial = entry.unique_id
    assert serial is not None

    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )
    device = VitaPower(unit, serial_number=serial)

    readings = VitaPowerDataUpdateCoordinator(
        hass,
        entry,
        entry.title,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = VitaPowerDataUpdateCoordinator(
        hass,
        entry,
        entry.title,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    await readings.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()
    entry.runtime_data = VitaPowerRuntimeData(readings, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

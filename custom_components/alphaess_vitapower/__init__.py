"""The AlphaESS VitaPower integration.

The Modbus link is borrowed from Home Assistant's own Modbus integration
(`modbus.async_get_unit`, Home Assistant 2026.10+). Every consumer of the same
host and port shares one TCP connection, which matters here: the VitaPower
accepts a single Modbus TCP client.
"""

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import CONF_UNIT_ID, CONNECT_DELAY, DOMAIN, MESSAGE_SPACING
from .coordinator import VitaPowerConfigEntry, VitaPowerCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:
    """Set up a VitaPower from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    try:
        unit = async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID])
    except HomeAssistantError as err:
        # Already held by another entry with link settings one shared
        # connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err
    unit.require_connect_delay(CONNECT_DELAY)
    unit.set_message_spacing(MESSAGE_SPACING)

    coordinator = VitaPowerCoordinator(hass, entry, unit)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:
    """Unload a config entry; the shared link closes behind its last user."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

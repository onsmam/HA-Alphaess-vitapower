"""Diagnostics for the AlphaESS VitaPower integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import VitaPowerConfigEntry
from .registers import SERIAL_ADDRESSES

TO_REDACT = {CONF_HOST, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VitaPowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw register cache is keyed like the ``addr`` column of the scans in
    ``docs/scans``, so a report can be compared against them. The registers
    holding the serial number are left out.
    """
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "unsupported_blocks": coordinator.unsupported_blocks,
        "values": async_redact_data(coordinator.data or {}, TO_REDACT),
        "registers": {
            f"0x{address:04X}": value
            for address, value in sorted(coordinator.registers.items())
            if address not in SERIAL_ADDRESSES
        },
    }

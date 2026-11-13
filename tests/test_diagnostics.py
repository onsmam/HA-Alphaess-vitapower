"""Tests for the AlphaESS VitaPower diagnostics."""

from unittest.mock import patch

from modbus_connection import ModbusConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot
    assert MOCK_SERIAL not in str(diag)


async def test_diagnostics_read_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test a failing raw read is reported rather than raised."""
    device = init_integration.runtime_data.readings.device
    with patch.object(
        device, "async_read_raw", side_effect=ModbusConnectionError("gone")
    ):
        diag = await get_diagnostics_for_config_entry(
            hass, hass_client, init_integration
        )

    assert diag["raw"] is None
    assert diag["read_error"] == "ModbusConnectionError"

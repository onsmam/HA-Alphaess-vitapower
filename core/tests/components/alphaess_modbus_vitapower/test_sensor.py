"""Tests for the AlphaESS VitaPower sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test all sensors match their snapshot."""
    with patch(
        "homeassistant.components.alphaess_modbus_vitapower.PLATFORMS",
        [Platform.SENSOR],
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the rarely needed limits start disabled."""
    for entity_id in (
        "sensor.vitapower_maximum_charge_current",
        "sensor.vitapower_maximum_feed_in",
        "sensor.vitapower_dispatch_duration",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

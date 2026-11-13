"""Tests for the AlphaESS VitaPower binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alphaess_modbus_vitapower.const import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_UNIT_ID


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test all binary sensors match their snapshot."""
    with patch(
        "homeassistant.components.alphaess_modbus_vitapower.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fault_bit_turns_the_sensor_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test any bit of a fault bitmask reports a problem."""
    assert hass.states.get("binary_sensor.vitapower_battery_fault").state == STATE_OFF

    mock_connection.for_unit(MOCK_UNIT_ID).holding[0x011F] = 0x0004
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.vitapower_battery_fault").state == STATE_ON

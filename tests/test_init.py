"""Tests for the AlphaESS VitaPower integration setup."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.alphaess_modbus_vitapower.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_OTHER_SERIAL, MOCK_SERIAL, MOCK_UNIT_ID, seed_vitapower


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the battery's device carries its identity."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "AlphaESS"
    assert device.model == "VitaPower 3600 AC"
    assert device.serial_number == MOCK_SERIAL
    assert device.sw_version == "1.1.24-CFU"


@pytest.mark.parametrize(
    "error", [ModbusConnectionError("refused"), ModbusTimeoutError()]
)
async def test_setup_retries_when_offline(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
    error: Exception,
) -> None:
    """Test a battery that does not answer at startup is retried."""
    mock_connection.for_unit(MOCK_UNIT_ID).fail_requests(error)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_another_battery(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
) -> None:
    """Test another serial at the address does not feed this entry."""
    seed_vitapower(mock_connection.for_unit(MOCK_UNIT_ID), MOCK_OTHER_SERIAL)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_refused_component_makes_only_its_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a component that stops answering takes only its own entities."""
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    unit.fail_read(0x0880, IllegalDataAddressError())

    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.vitapower_dispatch_power").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.vitapower_ac_power").state == "797"
    assert "dispatch failed to refresh" in caplog.text

    unit.fail_read(0x0880, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.vitapower_dispatch_power").state == "798"
    assert "dispatch is available again" in caplog.text


async def test_dead_link_makes_everything_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a dropped link takes every reading, and it comes back."""
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    unit.fail_requests(ModbusConnectionError("gone"))

    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.vitapower_ac_power").state == STATE_UNAVAILABLE

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.vitapower_ac_power").state == "797"


async def test_every_component_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a battery that refuses every block is a failed poll."""
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    for address in (0x0100, 0x0400, 0x0880, 0x08D4):
        unit.fail_read(address, IllegalDataAddressError())

    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    readings = init_integration.runtime_data.readings
    assert not readings.last_update_success
    assert hass.states.get("sensor.vitapower_battery_voltage").state == (
        STATE_UNAVAILABLE
    )

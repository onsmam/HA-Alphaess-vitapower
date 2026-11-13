"""Setup, polling and entities of the AlphaESS VitaPower integration."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusConnectionError
from modbus_connection.mock import MockModbusUnit, ReadEvent

from custom_components.alphaess_vitapower.const import DOMAIN
from custom_components.alphaess_vitapower.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.alphaess_vitapower.registers import BLOCKS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .conftest import SERIAL
from .scans import CHARGE_3680W, load_scan


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_entities(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """Entities carry the decoded scan; the device carries identity."""
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The link settings of the YAML hub that worked against this device.
    assert mock_unit.required_connect_delay == 1.0
    assert mock_unit.message_spacing == 0.03

    assert hass.states.get("sensor.vitapower_state_of_charge").state == "30.4"
    assert hass.states.get("sensor.vitapower_ac_power").state == "797"
    assert hass.states.get("sensor.vitapower_dc_battery_power").state == "857"
    assert hass.states.get("sensor.vitapower_energy_discharged").state == "0.9"
    assert hass.states.get("sensor.vitapower_conversion_efficiency").state == "93.0"
    assert hass.states.get("sensor.vitapower_dispatch_power").state == "798"
    assert hass.states.get("sensor.vitapower_inverter_firmware").state == "V3.05.011"
    assert hass.states.get("binary_sensor.vitapower_cloud_dispatch").state == STATE_ON
    fault = hass.states.get("binary_sensor.vitapower_battery_fault")
    assert fault.state == STATE_OFF
    assert fault.attributes["code"] == "0x00000000"
    cell = hass.states.get("sensor.vitapower_lowest_cell_voltage")
    assert cell.state == "3.225"
    # 18:12 scan: lowest cell is pack 2, cell 1 (0x0105/0x0106).
    assert cell.attributes["pack"] == 2
    assert cell.attributes["cell"] == 1

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "AlphaESS"
    assert device.model == "VitaPower 3600 AC"
    assert device.sw_version == "1.1.24-CFU"
    assert device.serial_number == SERIAL

    entity = er.async_get(hass).async_get("sensor.vitapower_relay_status_code")
    assert entity is not None
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_first_refresh_reads_every_block_once(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """One request per block, exactly the planned ranges."""
    await _setup(hass, mock_config_entry)
    assert mock_unit.read_events == [
        ReadEvent("holding", block.address, block.count) for block in BLOCKS
    ]


async def test_slow_blocks_wait_their_turn(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After 5 s only the power blocks are read again."""
    await _setup(hass, mock_config_entry)
    mock_unit.read_events.clear()
    mock_unit.holding.update(load_scan(CHARGE_3680W))

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {event.address for event in mock_unit.read_events} == {0x040C, 0x0126}
    assert hass.states.get("sensor.vitapower_ac_power").state == "-3679"
    # SOC is a 30 s block: still the old value.
    assert hass.states.get("sensor.vitapower_state_of_charge").state == "30.4"


async def test_unavailable_when_device_stops_answering(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A dead link makes the entities unavailable until it answers again."""
    await _setup(hass, mock_config_entry)
    mock_unit.fail_requests(ModbusConnectionError("gone"))
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vitapower_ac_power").state == STATE_UNAVAILABLE

    mock_unit.fail_requests(None)
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.vitapower_ac_power").state == "797"


async def test_refused_block_is_skipped(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """A block the firmware refuses only makes its own fields unknown."""
    mock_unit.fail_read(0x0880, IllegalDataAddressError(0x02, "illegal"))
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.vitapower_dispatch_power").state == "unknown"
    assert hass.states.get("sensor.vitapower_ac_power").state == "797"
    assert "dispatch" in mock_config_entry.runtime_data.unsupported_blocks


async def test_setup_retries_when_offline(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """No answer at startup: retry later."""
    mock_unit.fail_requests(ModbusConnectionError("refused"))
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_device(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """Another serial at the address does not feed this entry's entities."""
    mock_unit.holding[0x0749] = 0x3939
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_hide_serial(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """Neither the decoded nor the raw serial reaches diagnostics."""
    await _setup(hass, mock_config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics["values"]["serial_number"] == "**REDACTED**"
    assert diagnostics["entry"]["host"] == "**REDACTED**"
    assert "0x0743" not in diagnostics["registers"]
    assert diagnostics["registers"]["0x0102"] == 304
    assert SERIAL not in str(diagnostics)

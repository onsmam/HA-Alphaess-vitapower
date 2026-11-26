"""Tests for the AlphaESS VitaPower remote control (number and select)."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection, WriteEvent
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from homeassistant.components.alphaess_modbus_vitapower.const import KEEPALIVE_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_UNIT_ID

SETPOINT = "number.vitapower_power_setpoint"
MODE = "select.vitapower_control_mode"
STOP = [0, 0, 32000, 0, 32000, 0, 0, 0, 90, 255]


@pytest.fixture
def writes(mock_connection: MockModbusConnection) -> list[WriteEvent]:
    """Every write the integration sends to the battery."""
    events: list[WriteEvent] = []
    mock_connection.for_unit(MOCK_UNIT_ID).on_write(events.append)
    return events


def dispatch(events: list[WriteEvent]) -> list[list[int]]:
    """The dispatch blocks written, in order."""
    assert all(
        event.address == 0x0880 and event.function_code == 0x10 for event in events
    )
    return [list(event.values) for event in events]


async def _set_setpoint(hass: HomeAssistant, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: SETPOINT, ATTR_VALUE: value},
        blocking=True,
    )


async def _set_mode(hass: HomeAssistant, mode: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: MODE, ATTR_OPTION: mode},
        blocking=True,
    )


async def test_nothing_written_by_default(
    hass: HomeAssistant, writes: list[WriteEvent], init_integration: MockConfigEntry
) -> None:
    """Test a new entry leaves the battery to its own mode."""
    assert hass.states.get(MODE).state == "auto"
    assert hass.states.get(SETPOINT).state == "0"
    await _set_setpoint(hass, 2000)

    assert writes == []


async def test_charge(
    hass: HomeAssistant, writes: list[WriteEvent], init_integration: MockConfigEntry
) -> None:
    """Test a positive setpoint charges, to the charge cut-off."""
    await _set_setpoint(hass, 2000)
    await _set_mode(hass, "on")

    # 32000 - 2000 W; target 100 % (250 x 0.4 %); 300 s.
    assert dispatch(writes) == [[1, 0, 30000, 0, 32000, 2, 250, 0, 300, 255]]
    assert hass.states.get(MODE).state == "on"
    assert hass.states.get(SETPOINT).state == "2000"


async def test_discharge(
    hass: HomeAssistant, writes: list[WriteEvent], init_integration: MockConfigEntry
) -> None:
    """Test a negative setpoint discharges, to the discharge cut-off."""
    await _set_mode(hass, "on")
    await _set_setpoint(hass, -500)

    # On with setpoint 0 holds; then 32000 + 500 W to 10 % (25 x 0.4 %).
    assert dispatch(writes) == [
        [1, 0, 32000, 0, 32000, 2, 76, 0, 300, 255],
        [1, 0, 32500, 0, 32000, 2, 25, 0, 300, 255],
    ]


async def test_off_holds_idle(
    hass: HomeAssistant, writes: list[WriteEvent], init_integration: MockConfigEntry
) -> None:
    """Test off holds the battery at 0 W, at the state of charge it is at."""
    await _set_setpoint(hass, 3000)
    await _set_mode(hass, "off")

    # 0 W, target 30.4 % (76 x 0.4 %).
    assert dispatch(writes) == [[1, 0, 32000, 0, 32000, 2, 76, 0, 300, 255]]


async def test_auto_stops_a_running_command(
    hass: HomeAssistant, writes: list[WriteEvent], init_integration: MockConfigEntry
) -> None:
    """Test going back to the battery's own mode stops the dispatch once."""
    await _set_mode(hass, "off")
    await _set_mode(hass, "auto")
    await _set_mode(hass, "auto")

    assert dispatch(writes)[1:] == [STOP]


async def test_keepalive(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    writes: list[WriteEvent],
    init_integration: MockConfigEntry,
) -> None:
    """Test the command is written again before the battery ends it."""
    await _set_setpoint(hass, 1000)
    await _set_mode(hass, "on")

    freezer.tick(timedelta(seconds=KEEPALIVE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(writes) == 2
    assert writes[0] == writes[1]

    await _set_mode(hass, "auto")
    freezer.tick(timedelta(seconds=KEEPALIVE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert dispatch(writes)[2:] == [STOP]


async def test_resumes_after_restart(
    hass: HomeAssistant,
    writes: list[WriteEvent],
    mock_config_entry: MockConfigEntry,
    mock_get_unit: object,
) -> None:
    """Test the mode and setpoint come back and are written at once."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            # One cache for both: a second call would replace the first.
            (State(MODE, "on"), {}),
            (
                State(SETPOINT, "1500"),
                {
                    "native_max_value": 3680,
                    "native_min_value": -3680,
                    "native_step": 1,
                    "native_unit_of_measurement": "W",
                    "native_value": 1500,
                },
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(MODE).state == "on"
    assert hass.states.get(SETPOINT).state == "1500"
    assert dispatch(writes) == [[1, 0, 30500, 0, 32000, 2, 250, 0, 300, 255]]


async def test_write_failure(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a refused write is reported to the caller."""
    mock_connection.for_unit(MOCK_UNIT_ID).fail_write(
        0x0880, ModbusConnectionError("gone")
    )

    with pytest.raises(HomeAssistantError) as err:
        await _set_mode(hass, "off")

    assert err.value.translation_key == "write_failed"


async def test_override_is_logged_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a command written by another client is logged, once."""
    await _set_mode(hass, "off")
    # The vendor's cloud dispatches, as seen in a scan.
    mock_connection.for_unit(MOCK_UNIT_ID).holding.update(
        {0x0880: 1, 0x0881: 0, 0x0882: 32798, 0x0885: 2, 0x0886: 25, 0x0888: 180}
    )

    for _ in range(2):
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert caplog.text.count("another client replaced the dispatch command") == 1

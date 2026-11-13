"""Fixtures for the AlphaESS VitaPower integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.alphaess_modbus_vitapower.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL, MOCK_UNIT_ID, MOCK_USER_INPUT, seed_vitapower


@pytest.fixture(autouse=True)
def no_connect_delay() -> Generator[None]:
    """Skip the pause the library asks for after the link opens."""
    with patch(
        "custom_components.alphaess_modbus_vitapower.vendor.alphaess_modbus_vitapower.device.CONNECT_DELAY",
        0,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.alphaess_modbus_vitapower.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus TCP connection seeded as a discharging VitaPower."""
    connection = MockModbusConnection()
    seed_vitapower(connection.for_unit(MOCK_UNIT_ID))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an AlphaESS VitaPower config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_USER_INPUT,
        title="VitaPower",
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "custom_components.alphaess_modbus_vitapower.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the AlphaESS VitaPower integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Serialize registry entries and states the way Home Assistant does."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable every entity in the registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield

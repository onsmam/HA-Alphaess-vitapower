"""Fixtures: a VitaPower answering with a recorded scan, over the real
`homeassistant.components.modbus` connection sharing."""

from collections.abc import Generator
from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from custom_components.alphaess_vitapower.const import CONF_UNIT_ID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .scans import DISCHARGE_800W, load_scan

HOST = "192.168.1.28"
SERIAL = "ALG0REDACTED001"
USER_INPUT = {CONF_HOST: HOST, CONF_PORT: 502, CONF_UNIT_ID: 85}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


class ReopenableMockConnection(MockModbusConnection):
    """Stands in for every connection opened to the device.

    Home Assistant builds a new connection after the last holder closed the
    previous one; here that is the same object, so closing only drops the link.
    """

    async def close(self) -> None:
        await self.disconnect()


@pytest.fixture
def mock_connection() -> Generator[MockModbusConnection]:
    """Every link Home Assistant's Modbus integration opens is this one."""
    connection = ReopenableMockConnection()
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=connection,
    ):
        yield connection


@pytest.fixture
def mock_unit(mock_connection: MockModbusConnection) -> MockModbusUnit:
    """Unit 85, answering with the 18:12 discharge scan."""
    unit = mock_connection.for_unit(85)
    unit.holding.update(load_scan(DISCHARGE_800W))
    return unit


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A configured VitaPower."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="AlphaESS VitaPower",
        data=USER_INPUT,
        unique_id=SERIAL,
    )

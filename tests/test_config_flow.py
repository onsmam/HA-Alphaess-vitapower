"""Tests for the AlphaESS VitaPower config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import ModbusConnectionError, ModbusTcpParams
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alphaess_modbus_vitapower.const import DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import (
    MOCK_OTHER_SERIAL,
    MOCK_SERIAL,
    MOCK_UNIT_ID,
    MOCK_USER_INPUT,
    seed_vitapower,
)


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "custom_components.alphaess_modbus_vitapower.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a battery is added under its serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "VitaPower"
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a battery that does not answer, then does."""
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    unit.fail_requests(ModbusConnectionError("refused"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"error": "refused"}

    unit.fail_requests(None)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_link_in_use(hass: HomeAssistant) -> None:
    """Test a device already held over other link settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.alphaess_modbus_vitapower.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("in use"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_not_a_vitapower(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a device that answers without a serial number."""
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    for address in range(0x0743, 0x074B):
        unit.holding[address] = 0
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["errors"] == {"base": "not_a_vitapower"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the same battery at a new address updates the existing entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_USER_INPUT, CONF_HOST: "192.168.1.29"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.29"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pointing an entry at the address the battery moved to."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_USER_INPUT, CONF_HOST: "192.168.1.29"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.29"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_other_battery(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a different battery at the new address is refused."""
    seed_vitapower(mock_connection.for_unit(MOCK_UNIT_ID), MOCK_OTHER_SERIAL)
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure form shows a link failure, then recovers."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(MOCK_UNIT_ID)
    unit.fail_requests(ModbusConnectionError("refused"))
    result = await mock_config_entry.start_reconfigure_flow(hass)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["errors"] == {"base": "cannot_connect"}

    unit.fail_requests(None)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["reason"] == "reconfigure_successful"

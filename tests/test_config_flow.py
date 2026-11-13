"""Config flow of the AlphaESS VitaPower integration."""

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit

from custom_components.alphaess_vitapower.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import SERIAL, USER_INPUT


async def test_user_flow(hass: HomeAssistant, mock_unit: MockModbusUnit) -> None:
    """The serial number becomes the unique ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AlphaESS VitaPower"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """A device that does not answer shows an error, then recovers."""
    mock_unit.fail_requests(ModbusConnectionError("refused"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_serial(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Something answers, but not with a serial number."""
    for address in range(0x0743, 0x074B):
        mock_unit.holding[address] = 0
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "no_serial"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """The same address twice aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """The battery moved to another IP address."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.29"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.29"


async def test_reconfigure_other_device(
    hass: HomeAssistant, mock_unit: MockModbusUnit, mock_config_entry: MockConfigEntry
) -> None:
    """A different serial at the new address is refused."""
    mock_config_entry.add_to_hass(hass)
    mock_unit.holding[0x0749] = 0x3939  # "99"
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

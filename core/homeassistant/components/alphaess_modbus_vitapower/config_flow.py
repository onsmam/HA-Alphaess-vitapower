"""Config flow for AlphaESS VitaPower batteries."""

from collections.abc import Mapping
import logging
from typing import Any, override

from alphaess_modbus_vitapower import NotAVitaPowerError, VitaPower
from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The unit id every VitaPower answers on.
DEFAULT_UNIT_ID = 85

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            probatio.Coerce(int),
        ),
    }
)


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> VitaPower:
    """Connect to the battery and identify it, or raise."""
    async with async_get_temporary_unit(
        hass,
        ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT]),
        data[CONF_UNIT_ID],
    ) as unit:
        return await VitaPower.async_detect(unit)


class VitaPowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an AlphaESS VitaPower config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the battery is, then probe it."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            device, errors, description_placeholders = await self._async_validate(
                user_input
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at the address the battery moved to."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            device, errors, description_placeholders = await self._async_validate(
                user_input
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                # Another serial is a different battery, not a moved one.
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[VitaPower | None, dict[str, str], dict[str, str]]:
        """Probe the battery, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except NotAVitaPowerError:
            return None, {"base": "not_a_vitapower"}, {}
        except (ModbusError, HomeAssistantError) as err:
            return None, {"base": "cannot_connect"}, {"error": str(err)}
        return device, {}, {}

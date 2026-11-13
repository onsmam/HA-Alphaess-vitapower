"""Adding a VitaPower by address, and pointing one at a new address."""

import logging
from typing import Any

from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)
from .registers import BLOCKS, FIELDS_BY_KEY

_LOGGER = logging.getLogger(__name__)

_EMS_BLOCK = next(block for block in BLOCKS if block.key == "ems")

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


class VitaPowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AlphaESS VitaPower."""

    VERSION = 1

    async def _async_probe(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, dict[str, str]]:
        """Return the serial number answering at an address, or form errors."""
        params = ModbusTcpParams(host=user_input[CONF_HOST], port=user_input[CONF_PORT])
        try:
            async with async_get_temporary_unit(
                self.hass, params, user_input[CONF_UNIT_ID]
            ) as unit:
                values = await unit.read_holding_registers(
                    _EMS_BLOCK.address, _EMS_BLOCK.count
                )
        except HomeAssistantError:
            # Claimed by another entry with link settings one shared
            # connection cannot honour; retrying will not help.
            return None, {"base": "link_settings_in_use"}
        except ModbusError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception while probing the VitaPower")
            return None, {"base": "unknown"}

        serial = FIELDS_BY_KEY["serial_number"].decode(
            dict(zip(_EMS_BLOCK.addresses, values, strict=False))
        )
        if not isinstance(serial, str) or not serial.isprintable():
            return None, {"base": "no_serial"}
        return serial, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address and check a VitaPower answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                }
            )
            serial, errors = await self._async_probe(user_input)
            if serial is not None:
                # Stable across address changes, which a host or port is not.
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"{MANUFACTURER} {DEVICE_NAME}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at the address the VitaPower moved to."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            serial, errors = await self._async_probe(user_input)
            if serial is not None:
                await self.async_set_unique_id(serial)
                # Another serial is a different battery, not a moved one.
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

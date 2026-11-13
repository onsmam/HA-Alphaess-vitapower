"""Diagnostics support for AlphaESS VitaPower."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import VitaPowerConfigEntry

TO_REDACT = {CONF_HOST, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VitaPowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.readings.device
    raw = read_error = None
    try:
        raw = await device.async_read_raw(redact_serial=True)
    except ModbusError as err:
        read_error = type(err).__name__

    battery = device.battery
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "serial_number": device.serial_number,
            "firmware": {
                "ems": device.identity.ems_version,
                "inverter": device.identity.firmware_inverter,
                "arm": device.identity.firmware_arm,
                "bms": battery.bms_version,
            },
            "readings_failed": sorted(entry.runtime_data.readings.data.failed),
            "settings_failed": sorted(entry.runtime_data.settings.data.failed),
            "fault_codes": {
                "battery_warning": battery.warning,
                "battery_fault": battery.fault,
                "inverter_fault": device.inverter.fault,
                "system_fault": device.system.fault,
            },
            "cells": {
                "min_voltage": [
                    battery.min_cell_voltage_pack,
                    battery.min_cell_voltage_cell,
                ],
                "max_voltage": [
                    battery.max_cell_voltage_pack,
                    battery.max_cell_voltage_cell,
                ],
                "min_temperature": [
                    battery.min_cell_temperature_pack,
                    battery.min_cell_temperature_cell,
                ],
                "max_temperature": [
                    battery.max_cell_temperature_pack,
                    battery.max_cell_temperature_cell,
                ],
            },
            "read_error": read_error,
            "raw": raw,
        },
        TO_REDACT,
    )

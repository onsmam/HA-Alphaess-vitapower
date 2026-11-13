"""Polling the VitaPower, one register block at a time."""

import logging
import time
from typing import Any

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusError,
    ModbusUnit,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER, MODEL, UPDATE_INTERVAL
from .registers import BLOCKS, Block, decode_all

_LOGGER = logging.getLogger(__name__)

type VitaPowerConfigEntry = ConfigEntry[VitaPowerCoordinator]

# A block due within this margin is read now rather than one tick later.
_DUE_MARGIN = 0.5


class VitaPowerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read the blocks that are due and decode the register cache."""

    config_entry: VitaPowerConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: VitaPowerConfigEntry, unit: ModbusUnit
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=UPDATE_INTERVAL,
        )
        self.unit = unit
        self.registers: dict[int, int] = {}
        self._last_read: dict[str, float] = {}
        self.unsupported_blocks: dict[str, str] = {}

    def _due(self, block: Block, now: float) -> bool:
        if block.key in self.unsupported_blocks:
            return False
        last = self._last_read.get(block.key)
        return last is None or now - last >= block.interval - _DUE_MARGIN

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.monotonic()
        for block in BLOCKS:
            if not self._due(block, now):
                continue
            try:
                values = await self.unit.read_holding_registers(
                    block.address, block.count
                )
            except (IllegalDataAddressError, IllegalFunctionError) as err:
                # The firmware does not serve this range. Retrying every
                # interval only fills the log; its fields stay unknown.
                _LOGGER.warning(
                    "VitaPower refuses block %s (0x%04X, %d registers), skipping it: %s",
                    block.key,
                    block.address,
                    block.count,
                    err,
                )
                self.unsupported_blocks[block.key] = str(err)
                continue
            except ModbusError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={"error": str(err)},
                ) from err
            if len(values) != block.count:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="short_read",
                    translation_placeholders={
                        "block": block.key,
                        "expected": str(block.count),
                        "received": str(len(values)),
                    },
                )
            self.registers.update(zip(block.addresses, values, strict=True))
            self._last_read[block.key] = now

        data = decode_all(self.registers)

        # The address can be handed to another device (DHCP) after setup.
        serial = data["serial_number"]
        unique_id = self.config_entry.unique_id
        if serial and unique_id and serial != unique_id:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
                translation_placeholders={"serial": serial},
            )
        return data

    @property
    def device_info(self) -> DeviceInfo:
        """The VitaPower all entities of this entry belong to."""
        data = self.data or {}
        serial = self.config_entry.unique_id or self.config_entry.entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=DEVICE_NAME,
            serial_number=data.get("serial_number"),
            # Inverter, ARM and BMS firmware are diagnostic sensors.
            sw_version=data.get("ems_version"),
        )

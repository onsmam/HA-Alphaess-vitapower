"""Support for the AlphaESS VitaPower control mode."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONTROL_MODES
from .coordinator import VitaPowerConfigEntry, VitaPowerRuntimeData
from .entity import VitaPowerEntity, VitaPowerEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VitaPowerSelectDescription(VitaPowerEntityDescription, SelectEntityDescription):
    """Describe a VitaPower select."""


MODE_DESCRIPTION = VitaPowerSelectDescription(
    key="control_mode",
    translation_key="control_mode",
    component="dispatch",
    options=CONTROL_MODES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower select platform."""
    async_add_entities([VitaPowerModeSelect(entry.runtime_data, MODE_DESCRIPTION)])


class VitaPowerModeSelect(VitaPowerEntity, SelectEntity, RestoreEntity):
    """Whether Home Assistant controls the battery, and how."""

    entity_description: VitaPowerSelectDescription

    def __init__(
        self,
        runtime_data: VitaPowerRuntimeData,
        entity_description: VitaPowerSelectDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data, entity_description)
        self._controller = runtime_data.controller

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            last := await self.async_get_last_state()
        ) is not None and last.state in CONTROL_MODES:
            self._controller.mode = last.state
        self.async_on_remove(
            self._controller.async_add_listener(self.async_write_ha_state)
        )

    @property
    @override
    def current_option(self) -> str:
        return self._controller.mode

    @override
    async def async_select_option(self, option: str) -> None:
        await self._controller.async_set_mode(option)

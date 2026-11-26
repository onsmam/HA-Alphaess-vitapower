"""Support for the AlphaESS VitaPower power setpoint."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VitaPowerConfigEntry, VitaPowerRuntimeData
from .entity import VitaPowerEntity, VitaPowerEntityDescription
from .vendor.alphaess_modbus_vitapower import MAX_DISPATCH_POWER

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VitaPowerNumberDescription(VitaPowerEntityDescription, NumberEntityDescription):
    """Describe a VitaPower number."""


SETPOINT_DESCRIPTION = VitaPowerNumberDescription(
    key="power_setpoint",
    translation_key="power_setpoint",
    component="dispatch",
    native_min_value=-MAX_DISPATCH_POWER,
    native_max_value=MAX_DISPATCH_POWER,
    native_step=1,
    native_unit_of_measurement=UnitOfPower.WATT,
    device_class=NumberDeviceClass.POWER,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower number platform."""
    async_add_entities(
        [VitaPowerSetpointNumber(entry.runtime_data, SETPOINT_DESCRIPTION)]
    )


class VitaPowerSetpointNumber(VitaPowerEntity, RestoreNumber):
    """The power the battery should charge (+) or discharge (-) at.

    Followed while the control mode is on.
    """

    entity_description: VitaPowerNumberDescription

    def __init__(
        self,
        runtime_data: VitaPowerRuntimeData,
        entity_description: VitaPowerNumberDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data, entity_description)
        self._controller = runtime_data.controller

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            last := await self.async_get_last_number_data()
        ) is not None and last.native_value is not None:
            self._controller.setpoint = int(last.native_value)
        self.async_on_remove(
            self._controller.async_add_listener(self.async_write_ha_state)
        )

    @property
    @override
    def native_value(self) -> float:
        return self._controller.setpoint

    @override
    async def async_set_native_value(self, value: float) -> None:
        await self._controller.async_set_setpoint(round(value))

"""Base entity for AlphaESS VitaPower batteries."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VitaPowerDataUpdateCoordinator, VitaPowerRuntimeData


@dataclass(frozen=True, kw_only=True)
class VitaPowerEntityDescription(EntityDescription):
    """Describe a VitaPower entity."""

    component: str  # attribute name on VitaPower, e.g. 'battery', 'inverter'


def entity_unique_id(serial: str, key: str) -> str:
    """Name an entity by the battery's serial and its key."""
    return f"{serial}_{key}"


class VitaPowerEntity(CoordinatorEntity[VitaPowerDataUpdateCoordinator]):
    """Defines a base VitaPower entity."""

    _attr_has_entity_name = True
    entity_description: VitaPowerEntityDescription

    def __init__(
        self,
        runtime_data: VitaPowerRuntimeData,
        entity_description: VitaPowerEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        self._attr_unique_id = entity_unique_id(
            self.coordinator.device.serial_number, entity_description.key
        )
        self._attr_device_info = self.coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available or self.coordinator.data is None:
            return False
        return self.entity_description.component not in self.coordinator.data.failed

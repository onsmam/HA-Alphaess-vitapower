"""Base entity for the AlphaESS VitaPower integration."""

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VitaPowerCoordinator


class VitaPowerEntity(CoordinatorEntity[VitaPowerCoordinator]):
    """An entity of the one VitaPower a config entry describes."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VitaPowerCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        serial = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = coordinator.device_info

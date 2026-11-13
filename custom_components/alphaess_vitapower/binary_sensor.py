"""Binary sensors of the AlphaESS VitaPower: dispatch and fault flags."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VitaPowerConfigEntry
from .entity import VitaPowerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VitaPowerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a VitaPower binary sensor."""

    bitmask: bool = False
    """On for any non-zero code; the raw code goes in the attributes."""


def _problem(key: str) -> VitaPowerBinarySensorEntityDescription:
    return VitaPowerBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        bitmask=True,
    )


BINARY_SENSORS: tuple[VitaPowerBinarySensorEntityDescription, ...] = (
    VitaPowerBinarySensorEntityDescription(
        key="dispatch_active",
        translation_key="dispatch_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    _problem("battery_warning"),
    _problem("battery_fault"),
    _problem("inverter_fault"),
    _problem("system_fault"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitaPowerBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class VitaPowerBinarySensor(VitaPowerEntity, BinarySensorEntity):
    """A flag read from the VitaPower."""

    entity_description: VitaPowerBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the flag."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None
        return bool(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The raw code of a fault or warning bitmask."""
        if not self.entity_description.bitmask:
            return None
        value = self.coordinator.data.get(self.entity_description.key)
        return {"code": None if value is None else f"0x{value:08X}"}

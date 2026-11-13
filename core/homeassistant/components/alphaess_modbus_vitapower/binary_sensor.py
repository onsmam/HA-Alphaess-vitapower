"""Support for AlphaESS VitaPower binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from alphaess_modbus_vitapower import VitaPower

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VitaPowerConfigEntry
from .entity import VitaPowerEntity, VitaPowerEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VitaPowerBinarySensorDescription(
    VitaPowerEntityDescription, BinarySensorEntityDescription
):
    """Describe a VitaPower binary sensor."""

    value_fn: Callable[[VitaPower], bool | int | None]
    """A flag, or a bitmask that is on while any bit is set."""


def _fault(
    key: str, component: str, value_fn: Callable[[VitaPower], int | None]
) -> VitaPowerBinarySensorDescription:
    """A fault bitmask whose bits are undocumented: on for any of them."""
    return VitaPowerBinarySensorDescription(
        key=key,
        translation_key=key,
        component=component,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
    )


BINARY_SENSOR_DESCRIPTIONS: tuple[VitaPowerBinarySensorDescription, ...] = (
    VitaPowerBinarySensorDescription(
        key="dispatch_active",
        translation_key="dispatch_active",
        component="dispatch",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda device: device.dispatch.active,
    ),
    _fault("battery_warning", "battery", lambda device: device.battery.warning),
    _fault("battery_fault", "battery", lambda device: device.battery.fault),
    _fault("inverter_fault", "inverter", lambda device: device.inverter.fault),
    _fault("system_fault", "system", lambda device: device.system.fault),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower binary sensor platform."""
    async_add_entities(
        VitaPowerBinarySensor(entry.runtime_data, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class VitaPowerBinarySensor(VitaPowerEntity, BinarySensorEntity):
    """Defines a VitaPower binary sensor."""

    entity_description: VitaPowerBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        value = self.entity_description.value_fn(self.coordinator.device)
        return None if value is None else bool(value)

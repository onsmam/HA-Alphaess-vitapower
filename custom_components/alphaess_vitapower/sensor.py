"""Sensors of the AlphaESS VitaPower."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import VitaPowerConfigEntry
from .entity import VitaPowerEntity

# All entities read from the coordinator; nothing polls on its own.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VitaPowerSensorEntityDescription(SensorEntityDescription):
    """Describes a VitaPower sensor."""

    attributes: Mapping[str, str] | None = None
    """Extra state attributes: attribute name -> data key."""


def _power(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


def _energy(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        # Survives a reset at midnight, should the counters turn out to be
        # daily (docs: open point 1).
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        **kwargs,
    )


def _voltage(
    key: str, precision: int = 1, **kwargs: Any
) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=precision,
        **kwargs,
    )


def _current(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        **kwargs,
    )


def _temperature(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        **kwargs,
    )


def _percentage(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=PERCENTAGE,
        **kwargs,
    )


def _diagnostic(key: str, **kwargs: Any) -> VitaPowerSensorEntityDescription:
    """A raw value whose meaning is not (fully) known yet."""
    return VitaPowerSensorEntityDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.DIAGNOSTIC,
        **kwargs,
    )


SENSORS: tuple[VitaPowerSensorEntityDescription, ...] = (
    # --- energy dashboard
    VitaPowerSensorEntityDescription(
        key="soc",
        translation_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    _power("ac_power"),
    _power("dc_power"),
    _energy("energy_charged"),
    _energy("energy_discharged"),
    _energy("energy_charged_grid"),
    _percentage(
        "efficiency",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # --- battery
    _voltage("battery_voltage"),
    _current("battery_current"),
    _voltage(
        "cell_voltage_min",
        precision=3,
        attributes={"pack": "cell_voltage_min_pack", "cell": "cell_voltage_min_cell"},
    ),
    _voltage(
        "cell_voltage_max",
        precision=3,
        attributes={"pack": "cell_voltage_max_pack", "cell": "cell_voltage_max_cell"},
    ),
    _temperature(
        "cell_temperature_min",
        attributes={
            "pack": "cell_temperature_min_pack",
            "cell": "cell_temperature_min_cell",
        },
    ),
    _temperature(
        "cell_temperature_max",
        attributes={
            "pack": "cell_temperature_max_pack",
            "cell": "cell_temperature_max_cell",
        },
    ),
    _percentage(
        "soh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    _power("max_charge_power", entity_category=EntityCategory.DIAGNOSTIC),
    _power("max_discharge_power", entity_category=EntityCategory.DIAGNOSTIC),
    _current("max_charge_current", entity_category=EntityCategory.DIAGNOSTIC),
    _current("max_discharge_current", entity_category=EntityCategory.DIAGNOSTIC),
    _voltage(
        "max_charge_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _voltage(
        "min_discharge_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    VitaPowerSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    _diagnostic("module_count"),
    _diagnostic("battery_status", entity_registry_enabled_default=False),
    _diagnostic("relay_status", entity_registry_enabled_default=False),
    # --- inverter
    _voltage("grid_voltage"),
    _current("ac_current"),
    VitaPowerSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    _temperature("inverter_temperature"),
    _diagnostic("inverter_work_mode", entity_registry_enabled_default=False),
    # --- settings (read-only for now)
    _percentage("discharge_cutoff_soc"),
    _percentage("charge_cutoff_soc"),
    _percentage("max_feed_in", entity_category=EntityCategory.DIAGNOSTIC),
    # --- dispatch by the AlphaESS cloud
    _power("dispatch_power"),
    _percentage("dispatch_soc", suggested_display_precision=1),
    _diagnostic("dispatch_mode"),
    VitaPowerSensorEntityDescription(
        key="dispatch_duration",
        translation_key="dispatch_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- firmware
    _diagnostic("firmware_inverter"),
    _diagnostic("firmware_arm"),
    _diagnostic("bms_version"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitaPowerSensor(coordinator, description) for description in SENSORS
    )


class VitaPowerSensor(VitaPowerEntity, SensorEntity):
    """A value read from the VitaPower."""

    entity_description: VitaPowerSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the decoded register value."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Where the extreme cell sits, for the min/max cell sensors."""
        if not (attributes := self.entity_description.attributes):
            return None
        data = self.coordinator.data
        return {name: data.get(key) for name, key in attributes.items()}

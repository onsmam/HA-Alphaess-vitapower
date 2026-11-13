"""Support for AlphaESS VitaPower sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from alphaess_modbus_vitapower import VitaPower

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
from .entity import VitaPowerEntity, VitaPowerEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VitaPowerSensorDescription(VitaPowerEntityDescription, SensorEntityDescription):
    """Describe a VitaPower sensor."""

    value_fn: Callable[[VitaPower], StateType]


SENSOR_DESCRIPTIONS: tuple[VitaPowerSensorDescription, ...] = (
    # --- battery
    VitaPowerSensorDescription(
        key="state_of_charge",
        component="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.soc,
    ),
    VitaPowerSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        component="battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.voltage,
    ),
    VitaPowerSensorDescription(
        key="battery_current",
        translation_key="battery_current",
        component="battery",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.current,
    ),
    VitaPowerSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        component="battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery.dc_power,
    ),
    VitaPowerSensorDescription(
        key="state_of_health",
        translation_key="state_of_health",
        component="battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.soh,
    ),
    VitaPowerSensorDescription(
        key="min_cell_voltage",
        translation_key="min_cell_voltage",
        component="battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=lambda device: device.battery.min_cell_voltage,
    ),
    VitaPowerSensorDescription(
        key="max_cell_voltage",
        translation_key="max_cell_voltage",
        component="battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=lambda device: device.battery.max_cell_voltage,
    ),
    VitaPowerSensorDescription(
        key="min_cell_temperature",
        translation_key="min_cell_temperature",
        component="battery",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.min_cell_temperature,
    ),
    VitaPowerSensorDescription(
        key="max_cell_temperature",
        translation_key="max_cell_temperature",
        component="battery",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.max_cell_temperature,
    ),
    VitaPowerSensorDescription(
        key="max_charge_power",
        translation_key="max_charge_power",
        component="battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery.max_charge_power,
    ),
    VitaPowerSensorDescription(
        key="max_discharge_power",
        translation_key="max_discharge_power",
        component="battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery.max_discharge_power,
    ),
    VitaPowerSensorDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        component="battery",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.max_charge_current,
    ),
    VitaPowerSensorDescription(
        key="max_discharge_current",
        translation_key="max_discharge_current",
        component="battery",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.max_discharge_current,
    ),
    VitaPowerSensorDescription(
        key="capacity",
        translation_key="capacity",
        component="battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.capacity,
    ),
    # The battery updates these in batches, minutes behind; they are not live.
    VitaPowerSensorDescription(
        key="energy_charged",
        translation_key="energy_charged",
        component="battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.energy_charged,
    ),
    VitaPowerSensorDescription(
        key="energy_discharged",
        translation_key="energy_discharged",
        component="battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.energy_discharged,
    ),
    VitaPowerSensorDescription(
        key="energy_charged_from_grid",
        translation_key="energy_charged_from_grid",
        component="battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda device: device.battery.energy_charged_from_grid,
    ),
    # --- inverter
    VitaPowerSensorDescription(
        key="ac_power",
        translation_key="ac_power",
        component="inverter",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.inverter.ac_power,
    ),
    VitaPowerSensorDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        component="inverter",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.inverter.grid_voltage,
    ),
    VitaPowerSensorDescription(
        key="ac_current",
        translation_key="ac_current",
        component="inverter",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.inverter.ac_current,
    ),
    VitaPowerSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        component="inverter",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda device: device.inverter.grid_frequency,
    ),
    VitaPowerSensorDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        component="inverter",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.inverter.temperature,
    ),
    VitaPowerSensorDescription(
        key="efficiency",
        translation_key="efficiency",
        # Worked out from both the inverter's and the battery's power.
        component="inverter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.efficiency,
    ),
    # --- dispatch
    VitaPowerSensorDescription(
        key="dispatch_power",
        translation_key="dispatch_power",
        component="dispatch",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.dispatch.power,
    ),
    VitaPowerSensorDescription(
        key="dispatch_soc_target",
        translation_key="dispatch_soc_target",
        component="dispatch",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda device: device.dispatch.soc_target,
    ),
    VitaPowerSensorDescription(
        key="dispatch_duration",
        translation_key="dispatch_duration",
        component="dispatch",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.dispatch.duration,
    ),
    # --- settings
    VitaPowerSensorDescription(
        key="discharge_cutoff_soc",
        translation_key="discharge_cutoff_soc",
        component="settings",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.settings.discharge_cutoff_soc,
    ),
    VitaPowerSensorDescription(
        key="charge_cutoff_soc",
        translation_key="charge_cutoff_soc",
        component="settings",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.settings.charge_cutoff_soc,
    ),
    VitaPowerSensorDescription(
        key="max_feed_in",
        translation_key="max_feed_in",
        component="settings",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.settings.max_feed_in,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitaPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VitaPower sensor platform."""
    async_add_entities(
        VitaPowerSensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class VitaPowerSensor(VitaPowerEntity, SensorEntity):
    """Defines a VitaPower sensor."""

    entity_description: VitaPowerSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.device)

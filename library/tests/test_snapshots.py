"""Pin every decoded field and every read, per recorded scan."""

from __future__ import annotations

from typing import Any

import pytest
from modbus_connection.mock import MockModbusUnit
from modbus_connection.model import Component
from syrupy.assertion import SnapshotAssertion

from alphaess_modbus_vitapower import VitaPower

from .conftest import CHARGING, CHARGING_500W, DISCHARGING, SERIAL, seed


def decoded(component: Component) -> dict[str, Any]:
    """Each field's value, keyed by its name and absolute address."""
    return {
        f"{name} @ 0x{resolved.address:04X}": resolved.field.__get__(component)
        for name, resolved in component.resolved_fields.items()
    }


@pytest.mark.parametrize("scan", [DISCHARGING, CHARGING, CHARGING_500W])
async def test_scan(
    unit: MockModbusUnit, scan: str, snapshot: SnapshotAssertion
) -> None:
    seed(unit, scan)
    vitapower = VitaPower(unit, serial_number=SERIAL)

    await vitapower.async_update()

    assert {
        name: decoded(getattr(vitapower, name))
        for name in ("identity", *vitapower.readings_components)
        + vitapower.settings_components
    } == snapshot(name="decoded")
    assert [
        f"{event.register_type} 0x{event.address:04X} +{event.count}"
        for event in unit.read_events
    ] == snapshot(name="reads")
    assert vitapower.efficiency == snapshot(name="efficiency")

"""Fixtures: VitaPower batteries on modbus-connection's in-memory mock backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from alphaess_modbus_vitapower import DEFAULT_UNIT_ID, VitaPower

FIXTURES = Path(__file__).parent / "fixtures"

DISCHARGING = "discharging_800w_dispatch"
CHARGING = "charging_3680w"
CHARGING_500W = "charging_500w"

SERIAL = "ALG0REDACTED001"

# Where a real VitaPower answers with an exception, failing the whole block.
REFUSED = (0x0453, 0x0454, *range(0x072C, 0x0740))


def load_fixture(name: str) -> dict[str, Any]:
    """A recorded scan, as ``{"source": ..., "raw": {"holding": {...}}}``."""
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return data


def seed(unit: MockModbusUnit, name: str) -> None:
    """Answer like the battery did when the scan was taken."""
    unit.load_raw(load_fixture(name)["raw"])
    for address in REFUSED:
        unit.fail_read(address, IllegalDataAddressError())


@pytest.fixture
def unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """Unit 85, answering with the discharge scan."""
    unit = mock_modbus_connection.for_unit(DEFAULT_UNIT_ID)
    seed(unit, DISCHARGING)
    return unit


@pytest.fixture
def vitapower(unit: MockModbusUnit) -> VitaPower:
    """A VitaPower built from its known serial; nothing read yet."""
    return VitaPower(unit, serial_number=SERIAL)

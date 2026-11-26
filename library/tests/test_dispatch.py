"""Writing the dispatch block, checked against commands run on a real VitaPower."""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit, WriteEvent

from alphaess_modbus_vitapower import (
    MAX_DISPATCH_POWER,
    DispatchCommand,
    VitaPower,
)
from alphaess_modbus_vitapower.dispatch import STOP_REGISTERS

from .conftest import CHARGING, seed


def writes(unit: MockModbusUnit) -> list[WriteEvent]:
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    return events


@pytest.mark.parametrize(
    ("command", "registers"),
    [
        # Run on the battery: charge 3680 W to 12.8 % for 300 s.
        (
            DispatchCommand(power=-3680, target_soc=12.8, duration=300),
            (1, 0, 28320, 0, 32000, 2, 32, 0, 300, 255),
        ),
        # Run on the battery: discharge 500 W to the 10 % cut-off for 120 s.
        (
            DispatchCommand(power=500, target_soc=10, duration=120),
            (1, 0, 32500, 0, 32000, 2, 25, 0, 120, 255),
        ),
        # Run on the battery: hold idle at 15.6 % for 120 s.
        (
            DispatchCommand(power=0, target_soc=15.6, duration=120),
            (1, 0, 32000, 0, 32000, 2, 39, 0, 120, 255),
        ),
        # What the cloud wrote: discharge 798 W to 10 % for 180 s, but with
        # reactive power 32000 rather than the cloud's 0.
        (
            DispatchCommand(power=798, target_soc=10, duration=180),
            (1, 0, 32798, 0, 32000, 2, 25, 0, 180, 255),
        ),
        (
            DispatchCommand(power=3680, target_soc=100, duration=3600),
            (1, 0, 35680, 0, 32000, 2, 250, 0, 3600, 255),
        ),
    ],
)
def test_registers(command: DispatchCommand, registers: tuple[int, ...]) -> None:
    assert command.registers() == registers


@pytest.mark.parametrize(
    "kwargs",
    [
        {"power": MAX_DISPATCH_POWER + 1, "target_soc": 50, "duration": 60},
        {"power": -MAX_DISPATCH_POWER - 1, "target_soc": 50, "duration": 60},
        {"power": 0, "target_soc": 100.5, "duration": 60},
        {"power": 0, "target_soc": -1, "duration": 60},
        {"power": 0, "target_soc": 50, "duration": 0},
        {"power": 0, "target_soc": 50, "duration": 3601},
    ],
)
def test_rejects_what_the_battery_cannot_do(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        DispatchCommand(**kwargs)  # type: ignore[arg-type]


async def test_dispatch_is_one_fc16_write(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    events = writes(unit)
    command = DispatchCommand(power=-3680, target_soc=100, duration=300)

    await vitapower.async_dispatch(command)

    assert events == [WriteEvent("holding", 0x0880, list(command.registers()), 0x10)]
    assert vitapower.dispatch_command == command


async def test_stop_writes_what_the_battery_resets_to(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    events = writes(unit)
    await vitapower.async_dispatch(DispatchCommand(power=0, target_soc=50, duration=60))

    await vitapower.async_stop_dispatch()

    assert events[-1] == WriteEvent("holding", 0x0880, list(STOP_REGISTERS), 0x10)
    assert vitapower.dispatch_command is None
    # The battery's own reset, from the 18:20 scan.
    seed(unit, CHARGING)
    assert [unit.holding[a] for a in range(0x0880, 0x088A)] == list(STOP_REGISTERS)


async def test_running_command_is_not_overridden(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    command = DispatchCommand(power=-300, target_soc=100, duration=300)
    await vitapower.async_dispatch(command)

    await vitapower.async_update_readings()

    assert vitapower.dispatch.active is True
    assert not vitapower.dispatch_overridden


async def test_cloud_command_overrides(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_dispatch(
        DispatchCommand(power=-300, target_soc=100, duration=300)
    )
    # The cloud writes its own command, as in the 18:12 scan.
    unit.holding.update(
        {0x0880: 1, 0x0881: 0, 0x0882: 32798, 0x0885: 2, 0x0886: 25, 0x0888: 180}
    )

    await vitapower.async_update_readings()

    assert vitapower.dispatch_overridden


async def test_battery_ending_the_command_is_not_an_override(
    unit: MockModbusUnit, vitapower: VitaPower
) -> None:
    await vitapower.async_dispatch(
        DispatchCommand(power=-300, target_soc=100, duration=300)
    )
    unit.holding.update(dict(zip(range(0x0880, 0x088A), STOP_REGISTERS, strict=True)))

    await vitapower.async_update_readings()

    assert vitapower.dispatch.active is False
    assert not vitapower.dispatch_overridden


def test_not_overridden_before_anything_is_written(vitapower: VitaPower) -> None:
    assert not vitapower.dispatch_overridden

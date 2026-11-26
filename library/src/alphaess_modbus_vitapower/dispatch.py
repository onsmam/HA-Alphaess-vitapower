"""Remote dispatch, the 0x0880 register block."""

from __future__ import annotations

from dataclasses import dataclass

from modbus_connection.model import boolean, gauge, int32, integer, uint32

from .model import VitaPowerComponent

# Power is stored as P + 32000, so 32000 is 0 W.
DISPATCH_OFFSET = 32000


class Dispatch(VitaPowerComponent):
    """What the battery has been told to do over Modbus.

    The vendor's cloud writes this block itself, renewing it about every 180 s
    while it controls the battery; ``active`` tells whether a dispatch runs.
    Charging the battery from the vendor's app does not go through it.
    """

    active = boolean(0x0880)
    power = int32(0x0881, offset=-DISPATCH_OFFSET, nan=0, unit="W")
    """Positive discharges, negative charges.

    Both words 0 is not an offset value but "not set", so it reads as ``None``.
    """
    reactive_power = int32(0x0883, offset=-DISPATCH_OFFSET, nan=0, unit="var")
    """Written as 0, not 32000, while the cloud dispatches; that reads ``None``."""
    mode = integer(0x0885, signed=False)
    """2 while the cloud dispatches by state of charge, 0 when stopped."""
    soc_target = gauge(0x0886, 0.4, signed=False, unit="%")
    """In steps of 0.4 %: the cloud writes 25 for a 10 % cut-off."""
    duration = uint32(0x0887, unit="s")


# The address the whole command is written to, with one FC16 request.
DISPATCH_ADDRESS = 0x0880
# 2: charge or discharge at ``power`` until ``target_soc``; 0: stopped.
DISPATCH_MODE_SOC = 2
# 0x0889 reads 255 in every scan and every command the cloud wrote.
_FLOW = 255
# The step 0x0886 counts in: 25 is a 10 % target.
SOC_STEP = 0.4
# What the VitaPower 3600 AC charges and discharges at most.
MAX_DISPATCH_POWER = 3680
# A command ends on its own after its duration; keep it bounded.
MAX_DISPATCH_DURATION = 3600

# What the battery writes back itself when a dispatch ends, and what stops one.
STOP_REGISTERS: tuple[int, ...] = (
    0,
    0,
    DISPATCH_OFFSET,
    0,
    DISPATCH_OFFSET,
    0,
    0,
    0,
    90,
    _FLOW,
)


@dataclass(frozen=True, kw_only=True)
class DispatchCommand:
    """Charge, discharge or hold the battery for a while.

    ``power`` is positive to discharge and negative to charge, like the
    readings; 0 holds the battery idle. The battery ends the command itself
    after ``duration`` seconds, or once it reaches ``target_soc`` (it stops one
    0.4 % step short of it), and goes back to its own mode.
    """

    power: int
    target_soc: float
    duration: int

    def __post_init__(self) -> None:
        """Reject what the battery cannot do.

        Raises ``ValueError`` for a power beyond ``MAX_DISPATCH_POWER``, a
        target outside 0-100 % or a duration outside 1-``MAX_DISPATCH_DURATION`` s.
        """
        if not -MAX_DISPATCH_POWER <= self.power <= MAX_DISPATCH_POWER:
            raise ValueError(f"power {self.power} W is beyond ±{MAX_DISPATCH_POWER} W")
        if not 0 <= self.target_soc <= 100:
            raise ValueError(f"target SOC {self.target_soc} % is outside 0-100 %")
        if not 1 <= self.duration <= MAX_DISPATCH_DURATION:
            raise ValueError(
                f"duration {self.duration} s is outside 1-{MAX_DISPATCH_DURATION} s"
            )

    @property
    def soc_raw(self) -> int:
        """The target as written to 0x0886, in 0.4 % steps."""
        return round(self.target_soc / SOC_STEP)

    def registers(self) -> tuple[int, ...]:
        """The ten registers from 0x0880, high word first."""
        power = (self.power + DISPATCH_OFFSET) & 0xFFFF_FFFF
        return (
            1,
            power >> 16,
            power & 0xFFFF,
            0,
            DISPATCH_OFFSET,
            DISPATCH_MODE_SOC,
            self.soc_raw,
            self.duration >> 16,
            self.duration & 0xFFFF,
            _FLOW,
        )

    def runs_on(self, dispatch: Dispatch) -> bool:
        """Whether ``dispatch``, as last read, is still this command."""
        return (
            dispatch.active is True
            and dispatch.power == self.power
            and dispatch.mode == DISPATCH_MODE_SOC
            and dispatch.soc_target == round(self.soc_raw * SOC_STEP, 1)
            and dispatch.duration == self.duration
        )

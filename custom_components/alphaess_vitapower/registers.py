"""Register map of the AlphaESS VitaPower 3600 AC.

Pure Python, no Home Assistant imports, so it can be tested against the
register scans in ``docs/scans`` without a running Home Assistant.

All registers are holding registers (FC03), big-endian, 32-bit values with the
high word first. Sign convention: ``+`` = discharging, ``-`` = charging, which
is what the Home Assistant energy dashboard expects.

See ``docs/VITAPOWER_MODBUS.md`` for how every address was verified.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

type Registers = Mapping[int, int]
type DataType = Literal["u16", "i16", "u32", "i32", "str"]


@dataclass(frozen=True, kw_only=True)
class Block:
    """One block read, and how often it is due."""

    key: str
    address: int
    count: int
    interval: float
    """Seconds between reads."""

    @property
    def addresses(self) -> range:
        """The register addresses this block covers."""
        return range(self.address, self.address + self.count)


# Never part of a block read:
#   0x0453-0x0454 and 0x072C-0x073F answer with an exception (FC 0x83), which
#   fails the whole block.
#   0x0441-0x0449 change layout between charging and discharging.
#   0x0808-0x0810 hold the network/Modbus settings.
EXCLUDED_RANGES: tuple[range, ...] = (
    range(0x0441, 0x044A),
    range(0x0453, 0x0455),
    range(0x072C, 0x0740),
    range(0x0808, 0x0811),
)

IDENTITY_INTERVAL = 24 * 3600

BLOCKS: tuple[Block, ...] = (
    # 5 s: power
    Block(key="ac_power", address=0x040C, count=2, interval=5),
    Block(key="dc_power", address=0x0126, count=1, interval=5),
    # 30 s: SOC, voltage, current, dispatch
    Block(key="battery", address=0x0100, count=3, interval=30),
    Block(key="grid", address=0x0400, count=4, interval=30),
    Block(key="dispatch", address=0x0880, count=10, interval=30),
    # 60 s: cells, limits, counters, temperatures, faults
    Block(key="battery_detail", address=0x0103, count=0x0125 - 0x0103 + 1, interval=60),
    Block(key="battery_limits", address=0x012C, count=2, interval=60),
    Block(key="inverter", address=0x041C, count=0x0440 - 0x041C + 1, interval=60),
    Block(key="system_fault", address=0x08D4, count=2, interval=60),
    # 300 s: settings
    Block(key="feed_in", address=0x0800, count=1, interval=300),
    Block(key="soc_limits", address=0x0850, count=6, interval=300),
    # Identity: at start, then daily
    Block(key="firmware", address=0x0640, count=10, interval=IDENTITY_INTERVAL),
    Block(
        key="ems", address=0x0743, count=0x0750 - 0x0743 + 1, interval=IDENTITY_INTERVAL
    ),
)

IDENTITY_BLOCKS = frozenset({"firmware", "ems"})


@dataclass(frozen=True, kw_only=True)
class Field:
    """A value decoded from one or more registers."""

    key: str
    address: int
    data_type: DataType
    count: int = 1
    """Number of registers; only used for strings."""
    scale: float = 1
    offset: float = 0
    precision: int | None = None
    valid: Callable[[int], bool] | None = None
    """Return False for a raw value that must read as unknown."""

    @property
    def size(self) -> int:
        """Number of registers this field spans."""
        if self.data_type in ("u32", "i32"):
            return 2
        if self.data_type == "str":
            return self.count
        return 1

    @property
    def addresses(self) -> range:
        """The register addresses this field covers."""
        return range(self.address, self.address + self.size)

    def raw(self, registers: Registers) -> int | str | None:
        """Return the undecoded value, or None if a register is missing."""
        try:
            words = [registers[address] for address in self.addresses]
        except KeyError:
            return None
        match self.data_type:
            case "u16":
                return words[0]
            case "i16":
                return _signed(words[0], 16)
            case "u32":
                return (words[0] << 16) | words[1]
            case "i32":
                return _signed((words[0] << 16) | words[1], 32)
            case "str":
                return decode_string(words)

    def decode(self, registers: Registers) -> int | float | str | None:
        """Return the scaled value, or None if missing or invalid."""
        raw = self.raw(registers)
        if raw is None or isinstance(raw, str):
            return raw or None
        if self.valid is not None and not self.valid(raw):
            return None
        value = raw * self.scale + self.offset
        if self.precision is not None:
            return round(value, self.precision)
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value


def _signed(value: int, bits: int) -> int:
    """Interpret an unsigned integer as two's complement."""
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def decode_string(words: list[int]) -> str:
    """ASCII, two characters per register, high byte first, NUL padded."""
    data = b"".join(word.to_bytes(2, "big") for word in words)
    return data.replace(b"\x00", b"").decode("ascii", errors="replace").strip()


def _u16(
    key: str, address: int, scale: float = 1, precision: int | None = None
) -> Field:
    return Field(
        key=key, address=address, data_type="u16", scale=scale, precision=precision
    )


def _i16(
    key: str, address: int, scale: float = 1, precision: int | None = None
) -> Field:
    return Field(
        key=key, address=address, data_type="i16", scale=scale, precision=precision
    )


def _u32(
    key: str, address: int, scale: float = 1, precision: int | None = None
) -> Field:
    return Field(
        key=key, address=address, data_type="u32", scale=scale, precision=precision
    )


FIELDS: tuple[Field, ...] = (
    # --- core (energy dashboard)
    _u16("soc", 0x0102, 0.1, 1),
    Field(key="ac_power", address=0x040C, data_type="i32"),
    _i16("dc_power", 0x0126),
    _u32("energy_charged", 0x0120, 0.1, 1),
    _u32("energy_discharged", 0x0122, 0.1, 1),
    _u32("energy_charged_grid", 0x0124, 0.1, 1),
    # --- battery
    _u16("battery_voltage", 0x0100, 0.1, 1),
    _i16("battery_current", 0x0101, 0.1, 1),
    _u16("battery_status", 0x0103),
    _u16("relay_status", 0x0104),
    _u16("cell_voltage_min_pack", 0x0105),
    _u16("cell_voltage_min_cell", 0x0106),
    _u16("cell_voltage_min", 0x0107, 0.001, 3),
    _u16("cell_voltage_max_pack", 0x0108),
    _u16("cell_voltage_max_cell", 0x0109),
    _u16("cell_voltage_max", 0x010A, 0.001, 3),
    _u16("cell_temperature_min_pack", 0x010B),
    _u16("cell_temperature_min_cell", 0x010C),
    _i16("cell_temperature_min", 0x010D, 0.1, 1),
    _u16("cell_temperature_max_pack", 0x010E),
    _u16("cell_temperature_max_cell", 0x010F),
    _i16("cell_temperature_max", 0x0110, 0.1, 1),
    _u16("max_charge_current", 0x0111, 0.1, 1),
    _u16("max_discharge_current", 0x0112, 0.1, 1),
    _u16("max_charge_voltage", 0x0113, 0.1, 1),
    _u16("min_discharge_voltage", 0x0114, 0.1, 1),
    _u16("bms_version", 0x0115),
    _u16("module_count", 0x0118),
    _u16("capacity", 0x0119, 0.1, 1),
    _u16("soh", 0x011B, 0.1, 1),
    _u32("battery_warning", 0x011C),
    _u32("battery_fault", 0x011E),
    _u16("max_charge_power", 0x012C),
    _u16("max_discharge_power", 0x012D),
    # --- inverter
    _u16("grid_voltage", 0x0400, 0.1, 1),
    _u16("ac_current", 0x0403, 0.1, 1),
    _u16("grid_frequency", 0x041C, 0.01, 2),
    _i16("inverter_temperature", 0x0435, 0.1, 1),
    _u32("inverter_fault", 0x043A),
    _u16("inverter_work_mode", 0x0440),
    _u32("system_fault", 0x08D4),
    # --- settings
    _u16("max_feed_in", 0x0800),
    _u16("discharge_cutoff_soc", 0x0850),
    _u16("charge_cutoff_soc", 0x0855),
    # --- dispatch (AlphaESS cloud control)
    _u16("dispatch_start", 0x0880),
    Field(
        key="dispatch_power",
        address=0x0881,
        data_type="i32",
        offset=-32000,
        # Both words 0 is not an offset value but "not set".
        valid=lambda raw: raw != 0,
    ),
    _u16("dispatch_mode", 0x0885),
    _u16("dispatch_soc", 0x0886, 0.4, 1),
    _u32("dispatch_duration", 0x0887),
    # --- identity
    Field(key="firmware_inverter", address=0x0640, data_type="str", count=5),
    Field(key="firmware_arm", address=0x0645, data_type="str", count=5),
    Field(key="serial_number", address=0x0743, data_type="str", count=8),
    Field(key="ems_suffix", address=0x074E, data_type="str", count=3),
)

FIELDS_BY_KEY: dict[str, Field] = {field.key: field for field in FIELDS}

# Registers holding the serial number; kept out of diagnostics.
SERIAL_ADDRESSES = frozenset(FIELDS_BY_KEY["serial_number"].addresses)

# Below this the AC/DC ratio is dominated by standby consumption.
EFFICIENCY_MIN_POWER = 100


def ems_version(registers: Registers) -> str | None:
    """EMS version from 0x074B-0x074D plus the suffix at 0x074E-0x0750.

    For example ``1.1.24-CFU``.
    """
    try:
        major, minor, patch = (registers[a] for a in range(0x074B, 0x074E))
    except KeyError:
        return None
    version = f"{major}.{minor}.{patch}"
    if suffix := FIELDS_BY_KEY["ems_suffix"].decode(registers):
        version = f"{version}-{suffix}"
    return version


def efficiency(ac_power: Any, dc_power: Any) -> float | None:
    """AC/DC conversion efficiency in %.

    Discharging: AC out / DC in. Charging: DC in / AC out. Unknown below
    ``EFFICIENCY_MIN_POWER`` on either side or with opposite signs.
    """
    if not isinstance(ac_power, int | float) or not isinstance(dc_power, int | float):
        return None
    if abs(ac_power) < EFFICIENCY_MIN_POWER or abs(dc_power) < EFFICIENCY_MIN_POWER:
        return None
    if (ac_power > 0) != (dc_power > 0):
        return None
    ratio = ac_power / dc_power if ac_power > 0 else dc_power / ac_power
    return round(ratio * 100, 1)


def decode_all(registers: Registers) -> dict[str, Any]:
    """Decode every field, plus the values derived from them."""
    data: dict[str, Any] = {field.key: field.decode(registers) for field in FIELDS}
    data["ems_version"] = ems_version(registers)
    data["efficiency"] = efficiency(data["ac_power"], data["dc_power"])
    data["dispatch_active"] = (
        None if data["dispatch_start"] is None else data["dispatch_start"] == 1
    )
    return data


def _check_blocks() -> None:
    """Fail at import if a block covers an excluded register or misses a field."""
    covered: set[int] = set()
    for block in BLOCKS:
        for excluded in EXCLUDED_RANGES:
            if set(block.addresses) & set(excluded):
                raise ValueError(f"block {block.key} covers excluded {excluded}")
        covered.update(block.addresses)
    for field in FIELDS:
        if missing := set(field.addresses) - covered:
            raise ValueError(f"field {field.key} not read: {sorted(missing)}")
    if missing := set(range(0x074B, 0x074E)) - covered:
        raise ValueError(f"EMS version not read: {sorted(missing)}")


_check_blocks()

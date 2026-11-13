"""Tests for the AlphaESS VitaPower integration."""

from modbus_connection.mock import MockModbusUnit

from homeassistant.components.alphaess_modbus_vitapower.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "ALG0REDACTED001"
MOCK_OTHER_SERIAL = "ALG0REDACTED002"
MOCK_UNIT_ID = 85

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.28",
    CONF_PORT: 502,
    CONF_UNIT_ID: MOCK_UNIT_ID,
}

# A VitaPower 3600 AC discharging 797 W while the cloud dispatches 798 W,
# from a register scan of a real unit. Registers left out read 0.
DISCHARGING: dict[int, int] = {
    0x0100: 387,  # battery voltage -> 38.7 V
    0x0101: 232,  # battery current -> 23.2 A
    0x0102: 304,  # state of charge -> 30.4 %
    0x0103: 257,  # battery status
    0x0104: 3,  # relay status
    0x0105: 2,  # lowest cell voltage: pack 2
    0x0106: 1,  # lowest cell voltage: cell 1
    0x0107: 3225,  # lowest cell voltage -> 3.225 V
    0x0108: 1,
    0x0109: 1,
    0x010A: 3234,  # highest cell voltage -> 3.234 V
    0x010B: 3,
    0x010C: 4,
    0x010D: 140,  # lowest cell temperature -> 14.0 °C
    0x010E: 1,
    0x010F: 3,
    0x0110: 160,  # highest cell temperature -> 16.0 °C
    0x0111: 618,  # max charge current -> 61.8 A
    0x0112: 1567,  # max discharge current -> 156.7 A
    0x0113: 432,  # max charge voltage -> 43.2 V
    0x0114: 360,  # min discharge voltage -> 36.0 V
    0x0115: 102,  # BMS version
    0x0118: 3,  # modules
    0x0119: 120,  # capacity -> 12.0 kWh
    0x011B: 1000,  # state of health -> 100.0 %
    0x0123: 9,  # energy discharged -> 0.9 kWh
    0x0126: 857,  # battery power -> 857 W
    0x012C: 2399,  # max charge power -> 2399 W
    0x012D: 6075,  # max discharge power -> 6075 W
    0x0400: 2380,  # grid voltage -> 238.0 V
    0x0403: 33,  # AC current -> 3.3 A
    0x040D: 797,  # AC power -> 797 W
    0x041C: 4998,  # grid frequency -> 49.98 Hz
    0x0435: 270,  # inverter temperature -> 27.0 °C
    0x0440: 1,  # work mode
    0x0800: 100,  # max feed-in -> 100 %
    0x0850: 10,  # discharge cut-off -> 10 %
    0x0855: 100,  # charge cut-off -> 100 %
    0x0880: 1,  # dispatch active
    0x0882: 32798,  # dispatch power -> +798 W
    0x0885: 2,  # dispatch mode: by state of charge
    0x0886: 25,  # dispatch target -> 10.0 %
    0x0888: 180,  # dispatch duration -> 180 s
    0x074B: 1,  # EMS 1.1.24
    0x074C: 1,
    0x074D: 24,
}


def _seed_string(unit: MockModbusUnit, address: int, words: int, text: str) -> None:
    """Encode ASCII across consecutive registers, two characters each."""
    padded = text.ljust(words * 2, "\x00")
    for i in range(words):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[address + i] = (hi << 8) | lo


def seed_vitapower(unit: MockModbusUnit, serial: str = MOCK_SERIAL) -> None:
    """Seed a discharging VitaPower with its identity."""
    unit.holding.update(DISCHARGING)
    _seed_string(unit, 0x0640, 5, "V3.05.011")
    _seed_string(unit, 0x0645, 5, "V2.01.003")
    _seed_string(unit, 0x0743, 8, serial)
    _seed_string(unit, 0x074F, 2, "CFU")

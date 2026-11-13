# alphaess-modbus-vitapower

Read AlphaESS VitaPower AC-coupled batteries over Modbus, as typed Python
objects rather than register numbers.

The library maps the VitaPower's register set onto
[modbus-connection](https://github.com/home-assistant-libs/modbus-connection)'s device model:
you hand it a `ModbusUnit`, call `async_update()`, and read sub-systems as
attributes. It owns no connection and no I/O policy — the caller does.

## Supported devices

**`VitaPower` — the AlphaESS VitaPower 3600 AC.** A single-phase, AC-coupled
LFP battery (12S, 38.4 V nominal) of one to three 4 kWh modules, charging and
discharging at up to 3680 W. Verified against a 12 kWh unit running EMS
1.1.24-CFU, inverter firmware V3.05.011, ARM V2.01.003 and BMS 102.

The VitaPower answers Modbus TCP on its **LAN port only** (Wi-Fi exposes no
port 502), on **unit id 85**, with holding registers (FC03), big-endian, 32-bit
values high word first. It accepts **one TCP client at a time**: a second
connection is refused, so share one unit between everything that reads it.

Its map is AlphaESS's SMILE layout, with differences that the library handles:

- The serial number is at 0x0743 (mirrored at 0x0706). The ASCII string at
  0x064A, which SMILE maps read as the serial, is something else here.
- 0x012C and 0x012D hold the BMS charge and discharge power limits.
- 0x0441-0x0449 change layout between charging and discharging; nothing is read
  from them. `Inverter.ac_power` (0x040C) and `Battery.dc_power` (0x0126) cover
  the same ground.
- 0x0453-0x0454 and 0x072C-0x073F answer with an exception, which fails a whole
  block read. Each component declares the ranges the device serves, so a read
  never bridges into them.
- The grid meter, PV meter, PV strings, backup output and grid protection
  registers read 0 and are not modelled.

## Usage

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from alphaess_modbus_vitapower import DEFAULT_UNIT_ID, VitaPower


async def main() -> None:
    connection = ModbusConnection(ModbusTcpParams(host="192.168.1.28"))
    try:
        vitapower = await VitaPower.async_detect(connection.for_unit(DEFAULT_UNIT_ID))
        await vitapower.async_update()

        print("Serial:", vitapower.serial_number, vitapower.identity.ems_version)
        print("State of charge:", vitapower.battery.soc, "%")
        print("AC power:", vitapower.inverter.ac_power, "W")
        print("DC power:", vitapower.battery.dc_power, "W")
        print("Efficiency:", vitapower.efficiency, "%")
        print("Dispatched:", vitapower.dispatch.active, vitapower.dispatch.power, "W")
    finally:
        await connection.close()


asyncio.run(main())
```

Power and current are **positive while discharging and negative while
charging**, on both the AC side (`inverter.ac_power`) and the battery side
(`battery.dc_power`, `battery.current`). `inverter.ac_current` is always
positive.

A poll reads each sub-system independently: one refused block does not take
the rest of the poll with it. Every update method returns an `UpdateReport` — a
failed component keeps its previous values, does not notify its listeners, and
is listed by attribute name with its error, while every other component
refreshes and notifies once the whole poll is done. A dead link
(`ModbusConnectionError`) raises, and so does a timeout before any component has
answered, so a battery that is not responding is not walked block by block,
paying a timeout for each.

```python
report = await vitapower.async_update()
for name, error in report.failed.items():
    print(f"{name} kept its previous values: {error}")
```

| Component | Registers | What it holds |
| :--- | :--- | :--- |
| `battery` | 0x0100-0x012D | voltage, current, state of charge and health, cell extremes and where they sit, BMS limits, warning and fault bitmasks, energy counters, DC power |
| `inverter` | 0x0400-0x0440 | grid voltage, AC current and power, grid frequency, temperature, fault bitmask |
| `dispatch` | 0x0880-0x0888 | remote dispatch: active, power, state-of-charge target, mode, duration |
| `system` | 0x08D4-0x08D5 | system fault bitmask |
| `settings` | 0x0800, 0x0850-0x0855 | maximum feed-in, discharge and charge cut-off state of charge |
| `identity` | 0x0640-0x0649, 0x0743-0x0750 | serial number, inverter and ARM firmware, EMS version |

A readings poll costs four requests, the settings poll two, and the identity
two more, once.

### Measurements and settings refresh separately

`VitaPower` splits its poll by what it reads:

- `async_update_readings()` — what the battery measures: power, charge, cells,
  energy, dispatch, faults.
- `async_update_settings()` — what it has been configured to do: registers that
  change when something writes them, not on their own.
- `async_update()` — both, in one merged report.

```python
await vitapower.async_update_readings()  # every few seconds
await vitapower.async_update_settings()  # every few minutes
```

The first poll of any kind reads the identity. A failed identity read does not
fail the poll; it is tried again on each later readings poll that answers.

### The energy counters lag

`battery.energy_charged`, `energy_discharged` and `energy_charged_from_grid`
have a resolution of 0.1 kWh, rounded down, and the battery updates all three
together in batches, minutes behind what it has actually moved. They are not
live: integrate `ac_power` for that.

### The vendor's cloud dispatches

The `dispatch` block is how the battery is told what to do over Modbus, and
AlphaESS's own cloud uses it: while it controls the battery, `dispatch.active`
is True and the block is rewritten about every 180 s with the power it wants
(`power`, + discharge / − charge), a state-of-charge target and a duration.
Charging from the vendor's app does not go through it.

The block stores power as P + 32000. A stopped dispatch reads 32000, which is
0 W; the cloud leaves the reactive power at 0 rather than 32000, which reads as
`None` instead of −32000 var. The state-of-charge target is in 0.4 % steps: the
cloud writes 25 for a 10 % cut-off.

The library does not write yet. Nothing in it has been written to a VitaPower.

### Efficiency

No register holds the conversion efficiency, so `VitaPower.efficiency` works it
out from the last readings poll: AC over DC while discharging, DC over AC while
charging. Below 100 W on either side it is `None`, as standby draw dominates;
measured values run from 89 % at 500 W to 93 % at 800 W and 3.7 kW.

## Checking a real battery

`script/query.py` reads one VitaPower once and prints every value it serves,
which is the quickest way to see whether it is reachable and addressed
correctly:

```bash
# the battery's LAN port (502 and unit 85 are the defaults)
uv run script/query.py 192.168.1.28
# every register read, plus ranges the library does not model
uv run script/query.py 192.168.1.28 --raw --registers 0x0441:9 --registers 0x0889
```

The battery accepts one client: stop whatever else polls it first, or the
connection is refused. `--raw` adds every register it read, undecoded, which is
what an issue about a wrong value should quote; `async_read_raw(redact_serial=True)`
gives the same dump without the serial number. `--registers ADDR[:COUNT]` reads
any holding range raw, up to 125 registers per range, for checking a register
the library does not model yet. The script only reads.

## How long a request waits

The connection's default timeout, 10 seconds, applies. `VitaPower` asks the
link for a 1 s pause after it opens and a 30 ms gap around each request, which
is what the battery has been running with over its LAN port.

## Debug logging

The `alphaess_modbus_vitapower` logger says, at `DEBUG`, why an identity read
failed; a warning follows when three tries in a row did.

## Development

```bash
uv sync
```

```bash
uv run pytest
```

The tests run against recorded register scans of a real VitaPower in
`tests/fixtures`, with the serial number replaced.

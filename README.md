# AlphaESS VitaPower for Home Assistant

Read an **AlphaESS VitaPower 3600 AC** battery over Modbus TCP, on Home Assistant
**2026.10 or newer**, using the shared Modbus connections Home Assistant's
Modbus integration hands out (`homeassistant.components.modbus.async_get_unit`).

> [!WARNING]
> The readings have been checked against a real VitaPower and its app; the
> remote control has been tested on one VitaPower with scripts
> (`tools/vitapower_dispatch_test.py`), not yet through Home Assistant.
> Writing to the battery is at your own risk.

This repository holds three things:

| Folder | What | Modelled on |
| :--- | :--- | :--- |
| [`library/`](library) | `alphaess-modbus-vitapower`, the standalone device library on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection) | [darkrain-nl/sofar-modbus](https://github.com/darkrain-nl/sofar-modbus) |
| [`core/`](core) | the integration as it would be contributed to Home Assistant Core | [`homeassistant/components/sofar`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/sofar) |
| [`custom_components/`](custom_components) | the same integration for HACS, with the library vendored | [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint) |

`custom_components/` and `tests/` are generated from `core/` and `library/` by
[`scripts/sync_custom.py`](scripts/sync_custom.py); CI fails when they drift.

## Installation (HACS)

1. **Remove any other Modbus connection to the battery first** — such as a YAML
   `modbus:` hub — and restart. The VitaPower accepts a single Modbus TCP
   client, and a YAML hub opens a link of its own rather than sharing one.
2. HACS → ⋮ → **Custom repositories** → `https://github.com/onsmam/HA-Alphaess-vitapower`, type **Integration**.
3. Download **AlphaESS VitaPower (Modbus)** and restart Home Assistant.
4. **Settings → Devices & services → Add integration → AlphaESS VitaPower**:
   the IP address of the battery's **LAN port** (Wi-Fi serves no Modbus), port
   `502`, unit ID `85`.

The battery's serial number becomes the entry's unique ID; after an IP change use
**Reconfigure** on the integration.

## Entities

Power and current are **+ discharging, − charging**, as the energy dashboard
expects. Readings refresh every 5 s, the configured limits every 5 minutes.

| | Entities |
| :--- | :--- |
| Battery | state of charge, voltage, current, battery (DC) power, state of health, lowest/highest cell voltage and temperature, BMS charge/discharge power limits, capacity |
| Energy | energy charged, discharged, charged from grid (`total_increasing`; the battery updates them in batches, minutes behind) |
| Inverter | AC power, grid voltage, AC current, grid frequency, inverter temperature, conversion efficiency (worked out; unknown below 300 W) |
| Dispatch | remote dispatch running (the vendor's cloud controls the battery through it), dispatch power, state-of-charge target, duration |
| Settings | discharge and charge cut-off state of charge, maximum feed-in |
| Faults | battery warning, battery fault, inverter fault, system fault (on for any bit; the codes are in the diagnostics) |

For the energy dashboard: battery in `sensor.vitapower_energy_charged`, out
`sensor.vitapower_energy_discharged`, power `sensor.vitapower_ac_power`.

## Control (Day Ahead Optimizer)

Two entities control the battery through its dispatch block:

| Entity | What it does |
| :--- | :--- |
| `select.vitapower_control_mode` | `on`: follow the setpoint. `off`: hold the battery idle at 0 W. `auto` (default): write nothing, the battery follows the mode set in the app |
| `number.vitapower_power_setpoint` | W, **+ charges, − discharges** (as DAO writes it), −3680 to 3680 |

While the mode is `on` or `off` the command is written again every 60 s and
lasts 300 s in the battery: if Home Assistant stops, the battery takes control
back itself within 5 minutes. Charging aims for the charge cut-off and
discharging for the discharge cut-off, which the battery also enforces itself.
Both entities come back as they were after a restart. If another client — such
as the AlphaESS cloud — writes its own command, a warning is logged and the
command is written again at the next renewal.

### Wiring DAO

As in [DAO's AlphaESS examples](https://github.com/corneel27/day-ahead/wiki/09.-Voorbeelden-AlphaESS),
let DAO write three helpers and copy them over with an automation. Create:

| Helper | Type | Settings |
| :--- | :--- | :--- |
| `input_number.dao_vitapower_vermogen` | Number | −3680 to 3680, step 1, W |
| `input_select.dao_vitapower_modus` | Dropdown | `Aan`, `Uit` |
| `input_boolean.dao_vitapower_balanceren` | Toggle | |

In DAO's battery settings:

```json
"entity set power feedin": "input_number.dao_vitapower_vermogen",
"entity set operating mode": "input_select.dao_vitapower_modus",
```

and in its `grid` settings:

```json
"entity balance switch": "input_boolean.dao_vitapower_balanceren",
```

Leave `entity stop inverter` unset. The automation needs no timers, durations
or SOC targets: the integration renews the command and picks the targets.

[`examples/dao_vitapower_automation.yaml`](examples/dao_vitapower_automation.yaml)
is the automation, ready to paste in **Settings → Automations → Create
automation → ⋮ → Edit in YAML**. It checks, in this order:

| DAO | Control mode | Battery |
| :--- | :--- | :--- |
| balance switch on | `auto` | its own mode: with the app on self-consumption, it follows the grid meter to keep it at 0 |
| `Aan`, setpoint + or − | `on` | charges (+) or discharges (−) at the setpoint, up to 3680 W, also to feed in when prices are high |
| `Uit` | `off` | idle at 0 W, as DAO planned it |

DAO chooses per interval: a fixed setpoint follows its plan exactly, including
discharging at full power to sell, but the difference between its forecast and
the real house load goes to or comes from the grid; balancing makes up that
difference, but feeds in no more than the house uses. The automation also runs
when Home Assistant starts, so the battery is back on DAO's plan after a
restart.

For `Uit` to hand the battery back to the app instead (as in the wiki), use
`auto` in place of `off` in the automation's default.

#### With an EV charger

Balancing follows the grid meter, which also sees the car: while the car charges
the battery would discharge into it. [`examples/dao_vitapower_automation_ev.yaml`](examples/dao_vitapower_automation_ev.yaml)
replaces the automation above for a house with a charger. While the car charges
it recomputes every 15 s:

| DAO | Battery while the car charges |
| :--- | :--- |
| balance switch on | balances the house as if the car were not there: discharges what the house needs, or charges with the sun left over |
| `Aan`, − setpoint | discharges as DAO planned |
| `Aan`, + setpoint | charges as DAO planned, as far as the battery's phase stays within the main fuse (25 A) |
| `Uit` | idle at 0 W |

It needs the charger's status and power, the grid power, and the power, current
and voltage on the battery's phase; the file lists which entities to replace.
Because the battery's own power drops out of the sums, a copy that writes to two
helpers instead of the battery's entities shows what it would do without
touching the battery.

DAO may also be pointed at the two entities directly (`"entity set power feedin":
"number.vitapower_power_setpoint"`, `"entity set operating mode":
"select.vitapower_control_mode"`, with `"entity set operating mode on": "on"` and
`"entity set operating mode off": "off"`). That has not been tried; if DAO's log
reports `Fout bij schrijven naar …`, use the helpers.

Efficiency measured on the battery, for DAO's charge and discharge stages:
charging 89.7 % at 300 W and about 95 % at 3600 W (DC over AC); discharging
93 % at 800 W. Below a few hundred watts the readings are too coarse to tell.

## Development

The custom integration follows the blueprint:

```bash
scripts/setup
```

```bash
scripts/develop
```

```bash
scripts/lint
```

Change the integration in `core/` and the device in `library/`, then regenerate
`custom_components/` and `tests/` (needs `ruff` and a Home Assistant install for
the strings `[%key:…]` references resolve against):

```bash
python3 scripts/sync_custom.py
```

Run the custom integration's tests, and the library's:

```bash
pip install -r requirements_test.txt && pytest
```

```bash
cd library && uv sync && uv run pytest
```

[`docs/VITAPOWER_MODBUS.md`](docs/VITAPOWER_MODBUS.md) has the register map and
how it was verified; [`docs/scans`](docs/scans) the scans, with the serial
number replaced ([`tools/redact_scan.py`](tools/redact_scan.py)).
[`tools/modbus_scan.py`](tools/modbus_scan.py) is the read-only scanner they were
taken with, [`tools/vitapower_live.py`](tools/vitapower_live.py) prints every
value to compare with the app, [`tools/vitapower_dispatch_test.py`](tools/vitapower_dispatch_test.py)
runs one confirmed dispatch test, and [`examples/vitapower_yaml_package.yaml`](examples/vitapower_yaml_package.yaml)
the YAML package this replaces.

The icon and logo Home Assistant shows are in
`custom_components/alphaess_modbus_vitapower/brand/`; `scripts/sync_custom.py`
keeps them as they are.

## Releases

The HACS integration is released with bare version tags (`0.2.0`), the version
kept in [`custom_components/VERSION`](custom_components/VERSION); the library
with `library-` tags, see [`library/RELEASING.md`](library/RELEASING.md).

## Nederlands — snel installeren

1. Verwijder eerst je YAML `modbus:`-package voor de VitaPower en herstart (de batterij accepteert maar één client).
2. HACS → ⋮ → **Aangepaste repositories** → deze repo, type **Integratie** → downloaden → herstarten.
3. **Instellingen → Apparaten & diensten → Integratie toevoegen → AlphaESS VitaPower**: IP van de LAN-poort, poort 502, unit-ID 85.
4. Bediening via DAO: maak de drie helpers uit *Wiring DAO* hierboven, zet ze in DAO en plak [`examples/dao_vitapower_automation.yaml`](examples/dao_vitapower_automation.yaml) als automation (Instellingen → Automatiseringen → Nieuw → ⋮ → Bewerken in YAML).
   - DAO *balanceren* aan → *auto*: de batterij volgt zijn eigen modus (app op Eigen verbruik: nul op de meter).
   - DAO *Aan* → *on*: laden (+) of ontladen (−) op het vermogen van DAO, ook maximaal terugleveren.
   - DAO *Uit* → *off*: stil op 0 W.

   `Control mode` staat standaard op *auto*: er wordt niets geschreven tot DAO hem op Aan of Uit zet.
5. Laadpaal: gebruik [`examples/dao_vitapower_automation_ev.yaml`](examples/dao_vitapower_automation_ev.yaml). Terwijl de auto laadt balanceert de accu alsof de auto er niet is (geen accustroom naar de auto) en laadt hij alleen zolang zijn fase onder de 25 A blijft. Vervang de sensoren bovenin het bestand door die van jou.

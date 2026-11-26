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
let DAO write two helpers and copy them over with an automation. Create an
`input_number.dao_vitapower_vermogen` (−3680 to 3680, step 1, W) and an
`input_select.dao_vitapower_modus` (`Aan`, `Uit`), and in DAO's battery settings:

```json
"entity set power feedin": "input_number.dao_vitapower_vermogen",
"entity set operating mode": "input_select.dao_vitapower_modus",
```

Leave `entity stop inverter` unset. The automation needs no timers, durations
or SOC targets: the integration renews the command and picks the targets.

```yaml
automation:
  - alias: "DAO -> VitaPower"
    mode: queued
    triggers:
      - trigger: state
        entity_id:
          - input_number.dao_vitapower_vermogen
          - input_select.dao_vitapower_modus
    actions:
      - action: number.set_value
        target:
          entity_id: number.vitapower_power_setpoint
        data:
          value: "{{ states('input_number.dao_vitapower_vermogen') | int(0) }}"
      - action: select.select_option
        target:
          entity_id: select.vitapower_control_mode
        data:
          option: "{{ 'on' if is_state('input_select.dao_vitapower_modus', 'Aan') else 'auto' }}"
```

As in the wiki, DAO's `Uit` hands the battery back to the app: set the app to
self-consumption, so the battery serves the house between DAO's charge and
discharge hours. To hold it idle at 0 W instead, use `'off'` in place of
`'auto'` in the last line.

DAO may also be pointed at the two entities directly (`"entity set power feedin":
"number.vitapower_power_setpoint"`, `"entity set operating mode":
"select.vitapower_control_mode"`, with `"entity set operating mode on": "on"` and
`"entity set operating mode off": "auto"`). That has not been tried; if DAO's log
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

## Releases

The HACS integration is released with bare version tags (`0.2.0`), the version
kept in [`custom_components/VERSION`](custom_components/VERSION); the library
with `library-` tags, see [`library/RELEASING.md`](library/RELEASING.md).

## Nederlands — snel installeren

1. Verwijder eerst je YAML `modbus:`-package voor de VitaPower en herstart (de batterij accepteert maar één client).
2. HACS → ⋮ → **Aangepaste repositories** → deze repo, type **Integratie** → downloaden → herstarten.
3. **Instellingen → Apparaten & diensten → Integratie toevoegen → AlphaESS VitaPower**: IP van de LAN-poort, poort 502, unit-ID 85.
4. Bediening via DAO: zie *Wiring DAO* hierboven. `Control mode` staat standaard op *auto* (Batterij zelf): er wordt niets geschreven tot DAO hem op Aan zet. DAO *Uit* geeft de batterij terug aan de app; zet de app daarom op zelfverbruik.

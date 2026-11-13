# AlphaESS VitaPower for Home Assistant

Read an **AlphaESS VitaPower 3600 AC** battery over Modbus TCP, on Home Assistant
**2026.10 or newer**, using the shared Modbus connections Home Assistant's
Modbus integration hands out (`homeassistant.components.modbus.async_get_unit`).

> [!WARNING]
> Untested on hardware so far: everything has run against recorded register
> scans of a real VitaPower only. Read-only — nothing is written to the battery.

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
| Inverter | AC power, grid voltage, AC current, grid frequency, inverter temperature, conversion efficiency (worked out; unknown below 100 W) |
| Dispatch | remote dispatch running (the vendor's cloud controls the battery through it), dispatch power, state-of-charge target, duration |
| Settings | discharge and charge cut-off state of charge, maximum feed-in |
| Faults | battery warning, battery fault, inverter fault, system fault (on for any bit; the codes are in the diagnostics) |

For the energy dashboard: battery in `sensor.vitapower_energy_charged`, out
`sensor.vitapower_energy_discharged`, power `sensor.vitapower_ac_power`.

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
taken with, and [`examples/vitapower_yaml_package.yaml`](examples/vitapower_yaml_package.yaml)
the YAML package this replaces.

## Releases

The HACS integration is released with bare version tags (`0.2.0`), the version
kept in [`custom_components/VERSION`](custom_components/VERSION); the library
with `library-` tags, see [`library/RELEASING.md`](library/RELEASING.md).

## Nederlands — snel installeren

1. Verwijder eerst je YAML `modbus:`-package voor de VitaPower en herstart (de batterij accepteert maar één client).
2. HACS → ⋮ → **Aangepaste repositories** → deze repo, type **Integratie** → downloaden → herstarten.
3. **Instellingen → Apparaten & diensten → Integratie toevoegen → AlphaESS VitaPower**: IP van de LAN-poort, poort 502, unit-ID 85.

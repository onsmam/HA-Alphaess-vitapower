# AlphaESS VitaPower — Home Assistant Core integration

This folder mirrors [home-assistant/core](https://github.com/home-assistant/core):
copy both directories into a core checkout to contribute the integration.

```
homeassistant/components/alphaess_modbus_vitapower/   the integration
tests/components/alphaess_modbus_vitapower/           its tests
```

It follows the [`sofar`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/sofar)
integration: the device knowledge lives in the
[`alphaess-modbus-vitapower`](../library) library, and the integration borrows its
Modbus link from the Modbus integration (`homeassistant.components.modbus.async_get_unit`),
so every user of the battery shares one TCP connection — the VitaPower accepts a
single client.

- Two coordinators: readings every 5 s (`VitaPower.async_update_readings`),
  settings every 300 s (`async_update_settings`).
- Each entity names the library component it reads; a component that fails a
  poll makes only its own entities unavailable, logged once on failure and once
  on recovery.
- Config flow and reconfigure flow probe the battery through
  `async_get_temporary_unit` and key the entry on its serial number.
- Diagnostics carry the raw registers without the serial number.
- Read-only: nothing is written to the battery yet.

`.ruff.toml` and `tests/ruff.toml` are core's own Ruff configuration, so this
folder lints here as it will there (`ruff check core`).

## Before opening the pull request in core

The [`quality_scale.yaml`](homeassistant/components/alphaess_modbus_vitapower/quality_scale.yaml)
lists what is still `todo`:

1. **Publish the library** to PyPI (`library-0.1.0`, see
   [`library/RELEASING.md`](../library/RELEASING.md)) and keep
   `requirements` in `manifest.json` on that version.
2. **Snapshots**: `test_sensor.ambr` and `test_binary_sensor.ambr` are not
   included, as they are core's serializer's to write. In the core checkout:
   ```bash
   pytest tests/components/alphaess_modbus_vitapower --snapshot-update
   ```
3. Run `python3 -m script.hassfest` and `python3 -m script.translations develop`,
   which also adds the integration to the generated files (config flows,
   `CODEOWNERS`, `requirements_all.txt`).
4. **Documentation** on home-assistant.io (the `docs-*` rules) and **brand**
   images.
5. Get the integration tested on a working battery first: it has only run
   against recorded register scans.

The HACS version in [`custom_components/`](../custom_components) is generated
from this folder by [`scripts/sync_custom.py`](../scripts/sync_custom.py); change
the code here, not there.

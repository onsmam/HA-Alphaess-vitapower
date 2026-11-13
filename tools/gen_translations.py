#!/usr/bin/env python3
"""Write translations/en.json, translations/nl.json and strings.json.

One source for both languages, so the keys cannot drift apart.
Run: python3 tools/gen_translations.py
"""

import json
from pathlib import Path

ROOT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "alphaess_vitapower"
)

SENSORS = {
    "soc": ("State of charge", "Laadtoestand"),
    "ac_power": ("AC power", "AC-vermogen"),
    "dc_power": ("DC battery power", "DC-batterijvermogen"),
    "energy_charged": ("Energy charged", "Energie geladen"),
    "energy_discharged": ("Energy discharged", "Energie ontladen"),
    "energy_charged_grid": ("Energy charged from grid", "Energie geladen van net"),
    "efficiency": ("Conversion efficiency", "Rendement"),
    "battery_voltage": ("Battery voltage", "Batterijspanning"),
    "battery_current": ("Battery current", "Batterijstroom"),
    "cell_voltage_min": ("Lowest cell voltage", "Laagste celspanning"),
    "cell_voltage_max": ("Highest cell voltage", "Hoogste celspanning"),
    "cell_temperature_min": ("Lowest cell temperature", "Laagste celtemperatuur"),
    "cell_temperature_max": ("Highest cell temperature", "Hoogste celtemperatuur"),
    "soh": ("State of health", "Gezondheid (SOH)"),
    "max_charge_power": ("Max charge power", "Max laadvermogen"),
    "max_discharge_power": ("Max discharge power", "Max ontlaadvermogen"),
    "max_charge_current": ("Max charge current", "Max laadstroom"),
    "max_discharge_current": ("Max discharge current", "Max ontlaadstroom"),
    "max_charge_voltage": ("Max charge voltage", "Max laadspanning"),
    "min_discharge_voltage": ("Min discharge voltage", "Min ontlaadspanning"),
    "capacity": ("Capacity", "Capaciteit"),
    "module_count": ("Battery modules", "Batterijmodules"),
    "battery_status": ("Battery status code", "Batterijstatus (code)"),
    "relay_status": ("Relay status code", "Relaisstatus (code)"),
    "grid_voltage": ("Grid voltage", "Netspanning"),
    "ac_current": ("AC current", "AC-stroom"),
    "grid_frequency": ("Grid frequency", "Netfrequentie"),
    "inverter_temperature": ("Inverter temperature", "Omvormertemperatuur"),
    "inverter_work_mode": ("Inverter work mode code", "Werkmodus omvormer (code)"),
    "discharge_cutoff_soc": ("Discharge cut-off SOC", "Ontlaadgrens SOC"),
    "charge_cutoff_soc": ("Charge cut-off SOC", "Laadgrens SOC"),
    "max_feed_in": ("Max feed-in", "Max teruglevering"),
    "dispatch_power": ("Dispatch power", "Dispatch-vermogen"),
    "dispatch_soc": ("Dispatch SOC target", "Dispatch SOC-doel"),
    "dispatch_mode": ("Dispatch mode code", "Dispatch-modus (code)"),
    "dispatch_duration": ("Dispatch duration", "Dispatch-duur"),
    "firmware_inverter": ("Inverter firmware", "Firmware omvormer"),
    "firmware_arm": ("ARM firmware", "Firmware ARM"),
    "bms_version": ("BMS version", "BMS-versie"),
}
CELL_SENSORS = {
    "cell_voltage_min",
    "cell_voltage_max",
    "cell_temperature_min",
    "cell_temperature_max",
}

BINARY_SENSORS = {
    "dispatch_active": ("Cloud dispatch", "Cloud-dispatch"),
    "battery_warning": ("Battery warning", "Batterijwaarschuwing"),
    "battery_fault": ("Battery fault", "Batterijfout"),
    "inverter_fault": ("Inverter fault", "Omvormerfout"),
    "system_fault": ("System fault", "Systeemfout"),
}

EN, NL = 0, 1

TEXT = {
    "user_title": ("AlphaESS VitaPower", "AlphaESS VitaPower"),
    "user_description": (
        (
            "Enter the address of the VitaPower. Modbus TCP only answers on the LAN "
            "port, not over Wi-Fi. The battery accepts a single Modbus client: remove "
            "any other Modbus connection to it (such as a YAML `modbus:` hub) first."
        ),
        (
            "Vul het adres van de VitaPower in. Modbus TCP werkt alleen via de "
            "LAN-poort, niet via wifi. De batterij accepteert maar één Modbus-client: "
            "verwijder eerst elke andere Modbus-verbinding ernaartoe (zoals een YAML "
            "`modbus:`-hub)."
        ),
    ),
    "reconfigure_description": (
        "Update the address Home Assistant reaches this VitaPower at.",
        "Pas het adres aan waarop Home Assistant deze VitaPower bereikt.",
    ),
    "host": ("Host", "Host"),
    "port": ("Port", "Poort"),
    "unit_id": ("Unit ID", "Unit-ID"),
    "host_desc": (
        "IP address or hostname of the VitaPower (LAN port).",
        "IP-adres of hostnaam van de VitaPower (LAN-poort).",
    ),
    "port_desc": (
        "The Modbus TCP port, 502 by default.",
        "De Modbus TCP-poort, standaard 502.",
    ),
    "unit_id_desc": (
        "The VitaPower answers on unit ID 85.",
        "De VitaPower antwoordt op unit-ID 85.",
    ),
    "cannot_connect": (
        "Failed to connect. Check the address, that the LAN cable is used and that no other Modbus client is connected.",
        "Verbinden mislukt. Controleer het adres, of de LAN-kabel gebruikt wordt en of er geen andere Modbus-client verbonden is.",
    ),
    "link_settings_in_use": (
        "This address is already in use by another integration with different link settings.",
        "Dit adres wordt al door een andere integratie gebruikt met andere verbindingsinstellingen.",
    ),
    "no_serial": (
        "The device answers, but reports no serial number at 0x0743. Is it a VitaPower?",
        "Het apparaat antwoordt, maar geeft geen serienummer op 0x0743. Is het een VitaPower?",
    ),
    "unknown": ("Unexpected error", "Onverwachte fout"),
    "already_configured": (
        "Device is already configured",
        "Apparaat is al geconfigureerd",
    ),
    "reconfigure_successful": (
        "Re-configuration was successful",
        "Herconfiguratie geslaagd",
    ),
    "unique_id_mismatch": (
        "The device at this address has a different serial number. Enter the address of the same VitaPower.",
        "Het apparaat op dit adres heeft een ander serienummer. Vul het adres van dezelfde VitaPower in.",
    ),
    "exc_communication_error": (
        "Communication with the VitaPower failed: {error}",
        "Communicatie met de VitaPower mislukt: {error}",
    ),
    "exc_short_read": (
        "Block {block} returned {received} of {expected} registers.",
        "Blok {block} gaf {received} van {expected} registers terug.",
    ),
    "exc_wrong_device": (
        "A different device (serial {serial}) now answers at this address.",
        "Op dit adres antwoordt nu een ander apparaat (serienummer {serial}).",
    ),
    "exc_link_settings_in_use": (
        "The VitaPower is already in use with different link settings: {error}",
        "De VitaPower is al in gebruik met andere verbindingsinstellingen: {error}",
    ),
    "pack": ("Pack", "Pack"),
    "cell": ("Cell", "Cel"),
    "code": ("Code", "Code"),
}


def build(lang: int) -> dict:
    t = {k: v[lang] for k, v in TEXT.items()}
    data = {"host": t["host"], "port": t["port"], "unit_id": t["unit_id"]}
    data_description = {
        "host": t["host_desc"],
        "port": t["port_desc"],
        "unit_id": t["unit_id_desc"],
    }
    sensors = {}
    for key, names in SENSORS.items():
        sensors[key] = {"name": names[lang]}
        if key in CELL_SENSORS:
            sensors[key]["state_attributes"] = {
                "pack": {"name": t["pack"]},
                "cell": {"name": t["cell"]},
            }
    binary = {}
    for key, names in BINARY_SENSORS.items():
        binary[key] = {"name": names[lang]}
        if key != "dispatch_active":
            binary[key]["state_attributes"] = {"code": {"name": t["code"]}}
    return {
        "config": {
            "step": {
                "user": {
                    "title": t["user_title"],
                    "description": t["user_description"],
                    "data": data,
                    "data_description": data_description,
                },
                "reconfigure": {
                    "description": t["reconfigure_description"],
                    "data": data,
                    "data_description": data_description,
                },
            },
            "error": {
                "cannot_connect": t["cannot_connect"],
                "link_settings_in_use": t["link_settings_in_use"],
                "no_serial": t["no_serial"],
                "unknown": t["unknown"],
            },
            "abort": {
                "already_configured": t["already_configured"],
                "reconfigure_successful": t["reconfigure_successful"],
                "unique_id_mismatch": t["unique_id_mismatch"],
            },
        },
        "entity": {"binary_sensor": binary, "sensor": sensors},
        "exceptions": {
            "communication_error": {"message": t["exc_communication_error"]},
            "link_settings_in_use": {"message": t["exc_link_settings_in_use"]},
            "short_read": {"message": t["exc_short_read"]},
            "wrong_device": {"message": t["exc_wrong_device"]},
        },
    }


def write(path: Path, content: dict) -> None:
    path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    (ROOT / "translations").mkdir(exist_ok=True)
    write(ROOT / "strings.json", build(EN))
    write(ROOT / "translations" / "en.json", build(EN))
    write(ROOT / "translations" / "nl.json", build(NL))
    print("written")

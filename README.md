# AlphaESS VitaPower 3600 AC – Home Assistant (Modbus TCP)

Custom integratie voor de **AlphaESS VitaPower 3600 AC** via Modbus TCP, gebouwd op de
gedeelde Modbus-verbindingen die Home Assistant sinds **2026.10** aanbiedt
(`homeassistant.components.modbus.async_get_unit`, dezelfde basis als de core-integraties
`kaco_modbus` en `bluetti_modbus`).

- Config flow (UI), geen YAML.
- Leest alleen: v0.1 schrijft **niets** naar de batterij (zie [Roadmap](#roadmap)).
- Registermap en quirks: [`docs/VITAPOWER_MODBUS.md`](docs/VITAPOWER_MODBUS.md).
- Getest tegen de echte registerscans in [`docs/scans`](docs/scans) (serienummer daarin vervangen door `ALG0REDACTED001`).

## Vereisten

| | |
|---|---|
| Home Assistant | 2026.10.0 of nieuwer (ontwikkeld en getest met 2026.10.4 / bronnen van 2026.11.1) |
| Verbinding | LAN-poort van de VitaPower (wifi geeft geen poort 502) |
| Unit ID | 85 |
| Overige Modbus-clients | **Geen.** De VitaPower accepteert maar één TCP-client tegelijk. |

## Installatie (HACS)

1. HACS → ⋮ → **Custom repositories** → `https://github.com/onsmam/HA-Alphaess-vitapower`, type **Integration**.
2. Installeer **AlphaESS VitaPower (Modbus)** en herstart Home Assistant.
3. **Instellingen → Apparaten & diensten → Integratie toevoegen → AlphaESS VitaPower**.
4. Host `192.168.1.28`, poort `502`, unit ID `85`.

Het serienummer (0x0743) wordt de unique ID. Verandert het IP-adres: integratie → ⋮ → **Opnieuw configureren**.

## Overstappen van het YAML-package

De YAML-hub (`modbus:` in `packages/vitapower.yaml`) opent een **eigen** TCP-verbinding; die wordt
niet gedeeld met deze integratie. Omdat de VitaPower maar één client toestaat, moeten ze niet
naast elkaar draaien.

1. Verwijder `packages/vitapower.yaml` (of zet het `modbus:`- en `template:`-blok uit) en herstart.
2. Voeg de integratie toe (zie boven).
3. Pas energiedashboard en DAO aan naar de nieuwe entity-IDs (tabel hieronder).
4. Ruim de oude entities op (Instellingen → Entiteiten, filter op `vitapower`, status *niet beschikbaar*).

| Oud (YAML-package) | Nieuw |
|---|---|
| `sensor.vitapower_soc` | `sensor.vitapower_state_of_charge` |
| `sensor.vitapower_ac_vermogen` | `sensor.vitapower_ac_power` |
| `sensor.vitapower_dc_vermogen` | `sensor.vitapower_dc_battery_power` |
| `sensor.vitapower_geladen` | `sensor.vitapower_energy_charged` |
| `sensor.vitapower_ontladen` | `sensor.vitapower_energy_discharged` |
| `sensor.vitapower_geladen_van_net` | `sensor.vitapower_energy_charged_from_grid` |
| `sensor.vitapower_rendement` (template) | `sensor.vitapower_conversion_efficiency` |
| `sensor.vitapower_batterijspanning` | `sensor.vitapower_battery_voltage` |
| `sensor.vitapower_batterijstroom` | `sensor.vitapower_battery_current` |
| `sensor.vitapower_min_celspanning` / `max_celspanning` | `sensor.vitapower_lowest_cell_voltage` / `highest_cell_voltage` |
| `sensor.vitapower_min_celtemperatuur` / `max_celtemperatuur` | `sensor.vitapower_lowest_cell_temperature` / `highest_cell_temperature` |
| `sensor.vitapower_soh` | `sensor.vitapower_state_of_health` |
| `sensor.vitapower_max_laadvermogen` / `max_ontlaadvermogen` | `sensor.vitapower_max_charge_power` / `max_discharge_power` |
| `sensor.vitapower_netspanning` | `sensor.vitapower_grid_voltage` |
| `sensor.vitapower_ac_stroom` | `sensor.vitapower_ac_current` |
| `sensor.vitapower_netfrequentie` | `sensor.vitapower_grid_frequency` |
| `sensor.vitapower_omvormertemperatuur` | `sensor.vitapower_inverter_temperature` |
| `sensor.vitapower_dispatch_actief` | `binary_sensor.vitapower_cloud_dispatch` |
| `sensor.vitapower_dispatch_vermogen` | `sensor.vitapower_dispatch_power` |
| `sensor.vitapower_ontlaadgrens_soc` / `laadgrens_soc` | `sensor.vitapower_discharge_cut_off_soc` / `charge_cut_off_soc` |
| `sensor.vitapower_batterij_waarschuwing` / `batterij_fout` | `binary_sensor.vitapower_battery_warning` / `battery_fault` |
| `sensor.vitapower_omvormer_fout` / `systeem_fout` | `binary_sensor.vitapower_inverter_fault` / `system_fault` |
| `sensor.vitapower_firmware_omvormer` / `firmware_arm` | `sensor.vitapower_inverter_firmware` / `arm_firmware` |

Entity-IDs zijn Engels (HA genereert ze uit de Engelse naam); de weergavenamen zijn Nederlands
als je HA op Nederlands staat. De oude IDs zijn afgeleid van de namen in het YAML-package; controleer ze in je eigen installatie.

**Energiedashboard:** batterij in `sensor.vitapower_energy_charged`, uit `sensor.vitapower_energy_discharged`,
vermogen `sensor.vitapower_ac_power` (+ = ontladen, − = laden).

**DAO** (alleen de entity-velden wijzigen):

```json
"entity actual level": "sensor.vitapower_state_of_charge",
"upper limit": "sensor.vitapower_charge_cut_off_soc",
"lower limit": "sensor.vitapower_discharge_cut_off_soc",
```

## Entities

Teken vermogen/stroom: **+ = ontladen, − = laden**.

| Groep | Entities | Interval |
|---|---|---|
| Vermogen | AC-vermogen (0x040C), DC-batterijvermogen (0x0126), rendement (berekend) | 5 s |
| Batterij | SOC, spanning, stroom | 30 s |
| Net | netspanning, AC-stroom | 30 s |
| Dispatch | cloud-dispatch actief, vermogen, SOC-doel, modus, duur | 30 s |
| Cellen | laagste/hoogste celspanning en -temperatuur (attributen `pack`, `cell`) | 60 s |
| Tellers | energie geladen / ontladen / geladen van net (`total_increasing`) | 60 s |
| Limieten | max laad-/ontlaadvermogen en -stroom (BMS, dynamisch) | 60 s |
| Omvormer | netfrequentie, omvormertemperatuur | 60 s |
| Storingen | batterijwaarschuwing, batterijfout, omvormerfout, systeemfout (binary, attribuut `code`) | 60 s |
| Instellingen | ontlaadgrens SOC, laadgrens SOC, max teruglevering | 300 s |
| Identiteit | firmware omvormer/ARM, BMS-versie; EMS-versie en serienummer op het apparaat | start + 24 u |

Standaard uitgeschakeld (betekenis nog onbekend of zelden nodig): batterijstatus (0x0103),
relaisstatus (0x0104), werkmodus omvormer (0x0440), max laadspanning, min ontlaadspanning.

### Hoe er gelezen wordt

- Eén coördinator tikt elke 5 s en leest alleen de blokken die aan de beurt zijn: 2 requests per 5 s, de rest verspreid.
- Nooit gelezen: 0x0441–0x0449 (layout verschuift), 0x0453–0x0454 en 0x072C–0x073F (exception), 0x0808–0x0810 (netwerk). Dit wordt bij het laden van de integratie gecontroleerd.
- Weigert de firmware een blok toch (illegal address), dan wordt alleen dat blok overgeslagen en worden die entities *onbekend*; de rest blijft werken.
- Verbindingsinstellingen overgenomen van je werkende YAML-hub: 1 s wachten na verbinden, 30 ms tussen berichten.
- Geeft een ander apparaat (ander serienummer) antwoord op het adres, dan worden de entities niet gevoed.

### Diagnostiek

Integratie → ⋮ → **Diagnostiek downloaden** geeft de gedecodeerde waarden én de ruwe registercache
(zelfde adresnotatie als de scans). Serienummer en host worden weggelaten.

## Roadmap

1. **Bediening** (zodra de batterij gerepareerd is en getest kan worden):
   - number-entities voor ontlaadgrens (0x0850) en laadgrens (0x0855);
   - dispatch als één FC16-write van 9 registers vanaf 0x0880, korte duur + keep-alive, en stop;
   - write-allowlist; 0x0808–0x0810 en 0x1000–0x1024 nooit schrijven.
   Eerst uitzoeken welke app-modus de cloud-dispatch uitschakelt, anders overschrijven HA en de cloud elkaar elke ~180 s.
2. Open punten uit [`docs/VITAPOWER_MODBUS.md` §6](docs/VITAPOWER_MODBUS.md#6-open-punten): dag- of totaalteller, 0x0120 vs 0x0124, betekenis van 0x0103/0x0104/0x0440.

## Scannen

Zie [`tools/modbus_scan.py`](tools/modbus_scan.py) en §9 van het document. Omdat de VitaPower maar
één client toestaat: **integratie eerst uitschakelen** (⋮ → Uitschakelen), scannen, weer inschakelen.
Serienummer uit een scan halen voordat je hem deelt:

```bash
python3 tools/redact_scan.py scan_20261110_1812.csv
```

## Ontwikkeling

```bash
python3.14 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements_test.txt
```

```bash
.venv/bin/pytest
```

`custom_components/alphaess_vitapower/registers.py` bevat de volledige registermap zonder HA-afhankelijkheden.
Vertalingen (en/nl) worden gegenereerd met `python3 tools/gen_translations.py`.

[`examples/vitapower_yaml_package.yaml`](examples/vitapower_yaml_package.yaml) is het oude YAML-package, ter referentie.

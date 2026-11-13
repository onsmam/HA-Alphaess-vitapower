# AlphaESS VitaPower 3600 AC – Modbus TCP: bevindingen & specificatie

Overdrachtsdocument voor het bouwen van een Home Assistant-integratie op `modbus_connection`.
Gebaseerd op 9 volledige registerscans (10-11-2026, idle / ontladen 400–1550 W / laden 500 en 3680 W),
HA-history en vergelijking met [senalse/ha-alphaess-modbus](https://github.com/senalse/ha-alphaess-modbus) v1.14.0 (SMILE-registermap).

Bijgevoegd:
- `modbus_scan.py` – read-only scanner + diff (pymodbus)
- `vitapower.yaml` – huidig werkend HA-package (YAML-modbus, 29 sensoren + rendement-template)

---

## 1. Apparaat & verbinding

| | |
|---|---|
| Model | AlphaESS VitaPower 3600 AC, 12 kWh (3 modules × 4 kWh), AC-gekoppeld, 1-fase stekker |
| Batterij | LFP 12S, nominaal 38,4 V (36,0–43,2 V) |
| Max vermogen | 3680 W laden én ontladen (datasheet + gemeten) |
| Datasheet | 10.000 cycli, 10 jaar garantie, DoD 95 % |
| Firmware | EMS V1.1.24 (`CFU`), omvormer V3.05.011, ARM V2.01.003, BMS 102 |
| Protocol | **Modbus TCP alleen via de LAN-poort** (wifi geeft geen poort 502) |
| Adres | 192.168.1.28:502 (DHCP-reservering in Fritzbox), **unit ID 85** |
| Functiecode | FC03 holding registers, big-endian, 32-bit = hi-word eerst |
| Verbindingen | **Maar één TCP-client tegelijk.** Tweede client wordt geweigerd. |
| Geen meters | Grid-meter (0x0010–0x0042), PV-meter (0x0090–0x00B6), CT-ratio (0x0001, 0x0081): altijd 0 |

## 2. Conventies

- **Teken vermogen/stroom: + = ontladen, − = laden** (gelijk aan HA-energiedashboard).
- Registers die niet bestaan geven exception (FC 0x83): **0x0453–0x0454** en **0x072C–0x073F**. Niet in een blokread opnemen, anders faalt het hele blok.
- Tijd (0x0740–0x0742, kopie 0x0703–0x0705): per register 2 bytes binair: `YY MM`, `DD HH`, `mm ss` (0x1A0B = 26/11).
- Strings: ASCII, 2 tekens per register, hi-byte eerst, `\0`-padding.

## 3. Registermap – geverifieerd

### 3.1 Kern (energiedashboard)

| Reg | Type | Schaal | Eenheid | Betekenis | Verificatie |
|---|---|---|---|---|---|
| 0x0102 | u16 | 0,1 | % | SOC | 32,8 % = app |
| 0x040C–0D | i32 | 1 | W | **AC-vermogen totaal** | −3682 W bij 3680 W laden; +797 W ontladen |
| 0x0126 | i16 | 1 | W | DC-batterijvermogen | ≈ V × I; AC/DC ≈ 0,93 |
| 0x0120–21 | u32 | 0,1 | kWh | Energie geladen | loopt, zie §5 |
| 0x0122–23 | u32 | 0,1 | kWh | Energie ontladen | 0,7 kWh vs app 754 Wh |
| 0x0124–25 | u32 | 0,1 | kWh | Energie geladen van net | 0,5 terwijl 0x0120 = 0,4 (AC-kant?) |

### 3.2 Batterij (0x0100–0x0148)

| Reg | Type | Schaal | Eenheid | Betekenis | Waarde gezien |
|---|---|---|---|---|---|
| 0x0100 | u16 | 0,1 | V | Batterijspanning | 38,5–40,3 |
| 0x0101 | i16 | 0,1 | A | Batterijstroom (− = laden) | +23,2 / −91,7 |
| 0x0103 | u16 | – | – | Batterijstatus | 257 constant |
| 0x0104 | u16 | – | – | Relaisstatus | 3 |
| 0x0105/06 | u16 | – | – | Pack-/cel-ID laagste celspanning | |
| 0x0107 | u16 | 0,001 | V | Laagste celspanning | 3,209–3,347 |
| 0x0108/09 | u16 | – | – | Pack-/cel-ID hoogste celspanning | |
| 0x010A | u16 | 0,001 | V | Hoogste celspanning | 3,221–3,372 |
| 0x010B/0C | u16 | – | – | ID laagste celtemp | |
| 0x010D | i16 | 0,1 | °C | Laagste celtemperatuur | 13–16 |
| 0x010E/0F | u16 | – | – | ID hoogste celtemp | |
| 0x0110 | i16 | 0,1 | °C | Hoogste celtemperatuur | 15–18 |
| 0x0111 | u16 | 0,1 | A | Max laadstroom (BMS, **dynamisch**) | 61,9 idle/ontladen → 156,9 bij laden |
| 0x0112 | u16 | 0,1 | A | Max ontlaadstroom (BMS) | 156,7 |
| 0x0113 | u16 | 0,1 | V | Max laadspanning | 43,2 |
| 0x0114 | u16 | 0,1 | V | Min ontlaadspanning | 36,0 |
| 0x0115 | u16 | – | – | BMS-versie | 102 |
| 0x0118 | u16 | – | – | Aantal modules | 3 |
| 0x0119 | u16 | 0,1 | kWh | Capaciteit | 12,0 |
| 0x011B | u16 | 0,1 | % | SOH | 100,0 |
| 0x011C–1D | u32 | – | – | Batterij-waarschuwing (bitmask) | 0 |
| 0x011E–1F | u32 | – | – | Batterij-fout (bitmask) | 0 |
| 0x0127 | u16 | – | – | Resterende tijd (SMILE) | altijd 0 |
| **0x012C** | u16 | 1 | W | **Max laadvermogen** = 0x0100 × 0x0111 (VitaPower-specifiek) | 2393 → 6327 |
| **0x012D** | u16 | 1 | W | **Max ontlaadvermogen** = 0x0100 × 0x0112 (VitaPower-specifiek) | 6060–6327 |
| 0x0131–0x0147 | – | – | – | Alarmregisters | 0 |

### 3.3 Omvormer (0x0400–0x0452)

| Reg | Type | Schaal | Eenheid | Betekenis | Waarde gezien |
|---|---|---|---|---|---|
| 0x0400 | u16 | 0,1 | V | AC-spanning L1 (L2/L3 = 0) | 228–238 |
| 0x0403 | u16 | 0,1 | A | AC-stroom L1, **altijd positief** | 2,1–15,4 |
| 0x0406–07 | i32 | 1 | W | Vermogen L1 (= 0x040C) | |
| 0x040E | u16 | 0,1 | V | Waarschijnlijk backup/EPS-spanning | 228–237 |
| 0x0414–0x041A | – | – | – | Backup-vermogen | 0 |
| 0x041C | u16 | 0,01 | Hz | Netfrequentie | 49,97–50,00 |
| 0x041D–0x042B | – | – | – | PV-strings | 0 (geen PV-ingang) |
| 0x0435 | i16 | 0,1 | °C | Omvormertemperatuur | 26 → 37 bij 3,7 kW |
| 0x0436–0x043C | – | – | – | Omvormer-waarschuwing/fout | 0 |
| 0x043A–3B | u32 | – | – | Omvormer-fout (bitmask) | 0 |
| 0x043E | – | – | – | PV-energie | 0 |
| 0x0440 | u16 | – | – | Werkmodus | 1 constant |

**Niet gebruiken – 0x0441–0x0449 (VitaPower-specifiek, inconsistent):**
0x0441–43 = kopie DC V/I/P. Bij ontladen: 0x0445 klein ± getal (blindvermogen?), 0x0447 = |AC P|,
0x0448 = arbeidsfactor × 0,0001 (0,9996), 0x0449 = frequentie. Bij laden: 0x0447 = |AC P|,
**0x0448 = frequentie, 0x0449 = 0** → layout verschuift. 0x040C en 0x0126 dekken dit af.

### 3.4 Identificatie & systeem

| Reg | Type | Betekenis | Waarde |
|---|---|---|---|
| 0x0640 (5) | string | Omvormer-firmware | `V3.05.011` |
| 0x0645 (5) | string | ARM-firmware | `V2.01.003` |
| 0x064A (15) | string | **Niet** het serienummer (senalse leest hier SN) | `2608240715` |
| 0x0654 (3) | string | Onbekende firmware | `V0.025` |
| 0x0700 | u16 | ? | 100 |
| 0x0703–05 / 0x0740–42 | 3× u16 | Systeemtijd (§2) | klopt |
| 0x0706–0D / 0x0743–4A | string | **Serienummer** (15 tekens) | `ALG0…` |
| 0x0728–2B / 0x074B–4D | u16 | EMS-versie | 1.1.24 |
| 0x074F–50 | string | EMS-suffix | `CFU` |
| 0x1000 | u16 | Netregeling/landcode | 38 |
| 0x1001–0x1024 | – | Netbeveiliging OVP/UVP/OFP/UFP | 0 (niet beschikbaar) |

### 3.5 Instellingen (0x0800–0x0855)

| Reg | Type | Eenheid | Betekenis | Waarde |
|---|---|---|---|---|
| 0x0800 | u16 | % | Max teruglevering | 100 |
| 0x0805 | u16 | – | ? | 2 |
| 0x0808–0x0810 | – | – | **Netwerk: IP, masker, gateway, unit ID (85), baud** | **NOOIT schrijven** |
| 0x0850 | u16 | % | Ontlaadgrens SOC | 10 |
| 0x0855 | u16 | % | Laadgrens SOC | 100 |
| 0x08D0–0x08D5 | u32 | – | Systeemfout (0x08D4–D5) | 0 |

### 3.6 Dispatch (0x0880–0x088A) – sturing

| Reg | Type | Codering | Cloud stuurt (18:12) | Gestopt (18:20) |
|---|---|---|---|---|
| 0x0880 | u16 | 1 = start, 0 = stop | 1 | 0 |
| 0x0881–82 | i32 | **P + 32000** (+ = ontladen) | 32798 (= +798 W) | 32000 |
| 0x0883–84 | i32 | Q + 32000 | **0, 0** ← VitaPower-quirk | 0, 32000 |
| 0x0885 | u16 | Modus, **2 = SOC-sturing** | 2 | 0 |
| 0x0886 | u16 | SOC-doel × **0,4 %** (25 = 10 %) | 25 | 0 |
| 0x0887–88 | u32 | Duur in s | 180 | 90 |
| 0x0889 | u16 | ? | 255 | 255 |
| 0x0891 | u16 | Frequentie-dispatch | 0 | 0 |

- De **AlphaESS-cloud/AI stuurt actief via dit blok** en ververst elke ~180 s (0x0880 = 1, vermogen = gemeten AC).
- Handmatig laden via de app loopt **niet** via dispatch (0x0880 = 0 tijdens laden 3680 W).
- SOC-schaal 0,4 % bevestigd: cloud schrijft 25 = exact de ontlaadgrens 10 %. (senalse gebruikt 0,392.)

## 4. Gemeten rendement (AC ↔ DC)

| Situatie | AC | DC | Rendement |
|---|---|---|---|
| Laden 500 W | −499 | −446 | 0,894 |
| Laden 3680 W | −3682 | −3405 | 0,925 |
| Ontladen 700 W | +700 | +781 | 0,896 |
| Ontladen 800 W | +797 | +857 | 0,930 |
| Ontladen 1550 W | +1552 | +1677 | 0,925 |

Geen register voor rendement gevonden → berekenen: ontladen AC/DC, laden DC/AC, onder 100 W ongeldig.

## 5. Gedrag energietellers (0x0120 / 0x0122 / 0x0124)

- Resolutie 0,1 kWh, naar beneden afgerond.
- **Niet live: worden periodiek in één batch bijgewerkt** (alle drie tegelijk). Waargenomen stappen o.a. 18:28 en 18:40:51; achterstand t.o.v. app enkele tot ~15 minuten.
- Volgen de app (0,7 kWh vs 754 Wh; SOC-verloop klopt).
- `total_increasing` vangt een eventuele dagelijkse reset op.

## 6. Open punten

1. **Dag- of totaalteller?** Controleren of 0x0120/22/24 om 00:00 naar 0 gaan.
2. **0x0120 vs 0x0124**: DC- vs AC-kant? 0x0124 telt mogelijk alleen netladen.
3. **Dispatch schrijven is nog niet getest** op de VitaPower.
4. **Welke app-modus schakelt de cloud-dispatch uit?** Anders overschrijven HA en cloud elkaar (180 s).
5. Betekenis 0x0103 (257), 0x0104 (3), 0x0700, 0x0805, 0x040E, 0x0445, 0x064A/0x0654.
6. Update-interval van de energietellers exact bepalen.

## 7. Ontwerpnotities voor de integratie (`modbus_connection`)

- **Verbinding lenen** van een `modbus_connection` config entry (TCP, unit 85); nooit zelf openen. Lost het één-client-probleem op zolang alles via die entry loopt.
- **Blokreads** per groep, max ~100 registers; scans gebruikten 16-registerblokken zonder problemen. Groepen:
  `0x0100–0x012D`, `0x0400–0x0440`, `0x0640–0x0656` (strings), `0x0740–0x0750`, `0x0800–0x0810`, `0x0850–0x0855`, `0x0880–0x0889`, `0x08D4–0x08D5`, `0x1000`.
  **Uitsluiten:** 0x0453, 0x072C–0x073F, 0x0441–0x0449.
- **Pollintervallen**: vermogen 5 s, SOC/spanning/stroom 30 s, tellers/temperaturen/limieten 60 s, instellingen 300 s, firmware/SN bij start.
- **Device info** uit 0x0743 (SN, niet 0x064A) en 0x0640/0x0645/EMS-versie.
- **Niet aanmaken** (altijd 0 / niet aanwezig): grid- en PV-meter, PV-strings, PV-energie, backup, netbeveiliging, 0x0127.
- **Schrijven (later):** dispatch als één FC16-write van 9 registers vanaf 0x0880:
  `[1, 0, 32000+P, 0, 32000, 2, round(SOC/0.4), 0, duur]` (P: + ontladen / − laden, begrens ±3680).
  Stop: `[0, 0, 32000, 0, 32000, 0, 0, 0, 90]` (exact wat de batterij zelf terugzet).
  Korte duur (bijv. 300 s) + keep-alive elke 60–120 s → valt terug als HA uitvalt.
- **Write-denylist:** 0x0808–0x0810 (netwerk/Modbus), 0x1000–0x1024 (netbeveiliging), alles buiten dispatch/instellingen.
- **Quirks afvangen:** Q-offset 0x0883 (0 i.p.v. 32000 → niet als −32000 W tonen), SN-locatie, dynamische 0x0111.

## 8. Huidige HA-situatie (overbrugging)

- `vitapower.yaml` package: YAML-modbus hub `vitapower`, 29 sensoren + template `sensor.vitapower_rendement`.
  Hub stoppen/starten voor scans: `modbus.stop` / `modbus.restart` met `hub: vitapower`.
- Energiedashboard: in `sensor.vitapower_geladen`, uit `sensor.vitapower_ontladen`, vermogen `sensor.vitapower_ac_vermogen`,
  SOC `sensor.vitapower_soc`, bruikbare capaciteit 10,8 kWh.
- **DAO** (alleen plannen, geen stuur-entities):
  ```json
  {
    "name": "VitaPower",
    "entity actual level": "sensor.vitapower_soc",
    "capacity": 12,
    "upper limit": "sensor.vitapower_laadgrens_soc",
    "lower limit": "sensor.vitapower_ontlaadgrens_soc",
    "charge stages": [{"power":0,"efficiency":1},{"power":500,"efficiency":0.89},{"power":3680,"efficiency":0.925}],
    "discharge stages": [{"power":0,"efficiency":1},{"power":700,"efficiency":0.91},{"power":1550,"efficiency":0.925},{"power":3680,"efficiency":0.92}],
    "dc_to_bat efficiency": 0.95,
    "bat_to_dc efficiency": 0.95,
    "cycle cost": 0.03
  }
  ```
  Cycle cost: €2597 / (3650 cycli × 12 kWh × 2) ≈ 0,03 €/kWh. Ontlaadstage 3680 W is geschat.

## 9. Scannen

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install pymodbus
# eerst in HA: modbus.stop hub=vitapower
python3 modbus_scan.py --host 192.168.1.28 \
  --ranges 0x0001,0x0010-0x0042,0x0081,0x0090-0x00B6,0x0100-0x0148,0x0400-0x0454,0x0640-0x0658,0x0700-0x0760,0x0800-0x0891,0x08D0-0x08D5,0x1000-0x1024 \
  --out "scan_$(date +%Y%m%d_%H%M).csv"
python3 modbus_scan.py --diff scan_A.csv scan_B.csv
# daarna in HA: modbus.restart hub=vitapower
```

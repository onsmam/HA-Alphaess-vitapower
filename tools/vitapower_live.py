#!/usr/bin/env python3
"""Lees een AlphaESS VitaPower uit en toon de waarden leesbaar, om met de app te vergelijken.

Leest alleen - er wordt nooit geschreven.

Installatie (eenmalig, dezelfde venv als modbus_scan.py werkt ook):
    python3 -m venv .venv && source .venv/bin/activate && pip install pymodbus

Gebruik:
    python3 vitapower_live.py --host 192.168.1.151            # een keer
    python3 vitapower_live.py --host 192.168.1.151 --loop 10  # elke 10 s, Ctrl+C stopt
    python3 vitapower_live.py --host 192.168.1.151 --loop 10 --log vergelijk.csv

De VitaPower accepteert maar een Modbus-client: zet de Home Assistant-integratie
(of de YAML modbus-hub) eerst uit.
"""

import argparse
import csv
import datetime as dt
import sys
import time

# (start, aantal) - de blokken die de waarden hieronder bevatten
BLOCKS = [
    (0x0100, 0x014C - 0x0100),  # batterij, cellen, limieten, tellers, kandidaat moduletemp.
    (0x02E0, 9),  # serienummer module 1
    (0x02F0, 9),  # serienummer module 2
    (0x0300, 9),  # serienummer module 3
    (0x0400, 0x0441 - 0x0400),  # omvormer
    (0x0640, 0x0657 - 0x0640),  # firmware
    (0x0703, 3),  # klok
    (0x0743, 0x0751 - 0x0743),  # serienummer, EMS-versie
    (0x0800, 1),  # max teruglevering
    (0x0850, 6),  # SOC-grenzen
    (0x0880, 10),  # dispatch
    (0x08D4, 2),  # systeemfout
]


def connect(host, port):
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from pymodbus.client.sync import ModbusTcpClient  # pymodbus 2.x
    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        sys.exit(
            f"Geen verbinding met {host}:{port}. Draait er nog een andere "
            "Modbus-client (Home Assistant)? De VitaPower staat er maar een toe."
        )
    return client


def _read(client, address, count, unit):
    """Een blok holding registers, of None bij een fout."""
    for key in ("device_id", "slave", "unit"):  # pymodbus 3.x / 2.x
        try:
            rr = client.read_holding_registers(address, count=count, **{key: unit})
            break
        except TypeError:
            continue
    else:
        return None
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        return None
    return list(rr.registers)


def read_all(client, unit):
    regs = {}
    for start, count in BLOCKS:
        values = _read(client, start, count, unit)
        if values is None:  # blok geweigerd: per register, om het gat te vinden
            for address in range(start, start + count):
                one = _read(client, address, 1, unit)
                if one:
                    regs[address] = one[0]
        else:
            regs.update(zip(range(start, start + count), values))
    return regs


def u16(r, a):
    return r.get(a)


def i16(r, a):
    v = r.get(a)
    return None if v is None else (v - 0x10000 if v & 0x8000 else v)


def u32(r, a):
    hi, lo = r.get(a), r.get(a + 1)
    return None if hi is None or lo is None else (hi << 16) | lo


def i32(r, a):
    v = u32(r, a)
    return None if v is None else (v - 0x1_0000_0000 if v & 0x8000_0000 else v)


def text(r, a, n):
    if any(r.get(a + i) is None for i in range(n)):
        return None
    raw = b"".join(r[a + i].to_bytes(2, "big") for i in range(n))
    return raw.replace(b"\0", b"").decode("ascii", "replace").strip()


def scaled(v, factor, digits):
    return None if v is None else round(v * factor, digits)


def clock(r):
    parts = [r.get(a) for a in (0x0703, 0x0704, 0x0705)]
    if None in parts:
        return None
    ym, dh, ms = parts
    return f"20{ym >> 8:02}-{ym & 255:02}-{dh >> 8:02} {dh & 255:02}:{ms >> 8:02}:{ms & 255:02}"


def efficiency(ac, dc):
    if ac is None or dc is None or abs(ac) < 100 or abs(dc) < 100 or (ac > 0) != (dc > 0):
        return None
    return round((ac / dc if ac > 0 else dc / ac) * 100, 1)


def decode(r):
    """(sectie, naam, waarde, eenheid, register)"""
    ac, dc = i32(r, 0x040C), i16(r, 0x0126)
    dispatch_power = u32(r, 0x0881)
    ems = [u16(r, a) for a in (0x074B, 0x074C, 0x074D)]
    rows = [
        ("Batterij", "Laadtoestand (SOC)", scaled(u16(r, 0x0102), 0.1, 1), "%", "0x0102"),
        ("Batterij", "Spanning", scaled(u16(r, 0x0100), 0.1, 1), "V", "0x0100"),
        ("Batterij", "Stroom (+ ontladen)", scaled(i16(r, 0x0101), 0.1, 1), "A", "0x0101"),
        ("Batterij", "DC-vermogen (+ ontladen)", dc, "W", "0x0126"),
        ("Batterij", "Gezondheid (SOH)", scaled(u16(r, 0x011B), 0.1, 1), "%", "0x011B"),
        ("Batterij", "Capaciteit", scaled(u16(r, 0x0119), 0.1, 1), "kWh", "0x0119"),
        ("Batterij", "Aantal modules", u16(r, 0x0118), "", "0x0118"),
        ("Batterij", "BMS-versie", u16(r, 0x0115), "", "0x0115"),
        ("Batterij", "Status / relais", f"{u16(r, 0x0103)} / {u16(r, 0x0104)}", "", "0x0103/04"),
        ("Cellen", "Laagste celspanning", scaled(u16(r, 0x0107), 0.001, 3), "V",
         f"0x0107 (module {u16(r, 0x0105)}, cel {u16(r, 0x0106)})"),
        ("Cellen", "Hoogste celspanning", scaled(u16(r, 0x010A), 0.001, 3), "V",
         f"0x010A (module {u16(r, 0x0108)}, cel {u16(r, 0x0109)})"),
        ("Cellen", "Laagste celtemperatuur", scaled(i16(r, 0x010D), 0.1, 1), "°C",
         f"0x010D (module {u16(r, 0x010B)}, cel {u16(r, 0x010C)})"),
        ("Cellen", "Hoogste celtemperatuur", scaled(i16(r, 0x0110), 0.1, 1), "°C",
         f"0x0110 (module {u16(r, 0x010E)}, cel {u16(r, 0x010F)})"),
        ("Limieten", "Max laadstroom (BMS)", scaled(u16(r, 0x0111), 0.1, 1), "A", "0x0111"),
        ("Limieten", "Max ontlaadstroom (BMS)", scaled(u16(r, 0x0112), 0.1, 1), "A", "0x0112"),
        ("Limieten", "Max laadvermogen", u16(r, 0x012C), "W", "0x012C"),
        ("Limieten", "Max ontlaadvermogen", u16(r, 0x012D), "W", "0x012D"),
        ("Energie", "Geladen", scaled(u32(r, 0x0120), 0.1, 1), "kWh", "0x0120"),
        ("Energie", "Ontladen", scaled(u32(r, 0x0122), 0.1, 1), "kWh", "0x0122"),
        ("Energie", "Geladen van net", scaled(u32(r, 0x0124), 0.1, 1), "kWh", "0x0124"),
        ("Omvormer", "AC-vermogen (+ ontladen)", ac, "W", "0x040C"),
        ("Omvormer", "Netspanning", scaled(u16(r, 0x0400), 0.1, 1), "V", "0x0400"),
        ("Omvormer", "AC-stroom", scaled(u16(r, 0x0403), 0.1, 1), "A", "0x0403"),
        ("Omvormer", "Netfrequentie", scaled(u16(r, 0x041C), 0.01, 2), "Hz", "0x041C"),
        ("Omvormer", "Temperatuur", scaled(i16(r, 0x0435), 0.1, 1), "°C", "0x0435"),
        ("Omvormer", "Rendement (berekend)", efficiency(ac, dc), "%", "0x040C/0x0126"),
        ("Omvormer", "0x040E (EPS-spanning?)", scaled(u16(r, 0x040E), 0.1, 1), "V", "0x040E"),
        ("Omvormer", "0x0411 (onbekend)", u16(r, 0x0411), "", "0x0411"),
        ("Dispatch", "Actief", u16(r, 0x0880), "", "0x0880"),
        ("Dispatch", "Vermogen", None if not dispatch_power else dispatch_power - 32000, "W", "0x0881"),
        ("Dispatch", "Modus", u16(r, 0x0885), "", "0x0885"),
        ("Dispatch", "SOC-doel", scaled(u16(r, 0x0886), 0.4, 1), "%", "0x0886"),
        ("Dispatch", "Duur", u32(r, 0x0887), "s", "0x0887"),
        ("Instellingen", "Ontlaadgrens SOC", u16(r, 0x0850), "%", "0x0850"),
        ("Instellingen", "Laadgrens SOC", u16(r, 0x0855), "%", "0x0855"),
        ("Instellingen", "Max teruglevering", u16(r, 0x0800), "%", "0x0800"),
        ("Storingen", "Batterij waarschuwing / fout",
         f"{u32(r, 0x011C)} / {u32(r, 0x011E)}", "", "0x011C/0x011E"),
        ("Storingen", "Omvormer / systeem fout", f"{u32(r, 0x043A)} / {u32(r, 0x08D4)}", "",
         "0x043A/0x08D4"),
        ("Identiteit", "Serienummer omvormer", text(r, 0x0743, 8), "", "0x0743"),
        ("Identiteit", "EMS-versie",
         None if None in ems else f"{ems[0]}.{ems[1]}.{ems[2]}-{text(r, 0x074F, 2)}", "", "0x074B"),
        ("Identiteit", "Firmware omvormer", text(r, 0x0640, 5), "", "0x0640"),
        ("Identiteit", "Firmware ARM", text(r, 0x0645, 5), "", "0x0645"),
        ("Identiteit", "0x064A (onbekend)", text(r, 0x064A, 5), "", "0x064A"),
        ("Identiteit", "0x0654 (onbekend)", text(r, 0x0654, 3), "", "0x0654"),
        ("Identiteit", "Klok batterij", clock(r), "", "0x0703"),
    ]
    for n, (serial_at, temp_at) in enumerate(((0x02E0, 0x0149), (0x02F0, 0x014A), (0x0300, 0x014B)), 1):
        rows.append(("Modules", f"Module {n} serienummer", text(r, serial_at, 9), "", f"0x{serial_at:04X}"))
        rows.append(("Modules", f"Module {n} temperatuur? (x0,1)", scaled(i16(r, temp_at), 0.1, 1), "°C",
                     f"0x{temp_at:04X} NIET BEVESTIGD"))
    return rows


def show(rows, when):
    print(f"\n=== VitaPower {when:%Y-%m-%d %H:%M:%S} ===")
    section = None
    for sec, name, value, unit, reg in rows:
        if sec != section:
            section = sec
            print(f"\n{sec}")
        shown = "—" if value is None else f"{value} {unit}".strip()
        print(f"  {name:<32} {shown:<22} [{reg}]")


def log(path, rows, when):
    new = False
    try:
        new = open(path).read(1) == ""
    except FileNotFoundError:
        new = True
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["tijd", *[f"{sec}: {name} [{unit}]" for sec, name, _, unit, _ in rows]])
        w.writerow([when.isoformat(timespec="seconds"), *[value for _, _, value, _, _ in rows]])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="192.168.1.151")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=85)
    p.add_argument("--loop", type=float, metavar="SEC", help="herhaal elke SEC seconden")
    p.add_argument("--log", metavar="CSV", help="schrijf elke meting als regel in dit CSV-bestand")
    args = p.parse_args()

    client = connect(args.host, args.port)
    try:
        while True:
            when = dt.datetime.now()
            regs = read_all(client, args.unit)
            if not regs:
                sys.exit("Niets gelezen: klopt het unit-ID (85) en het IP-adres?")
            rows = decode(regs)
            show(rows, when)
            if args.log:
                log(args.log, rows, when)
            if not args.loop:
                break
            time.sleep(args.loop)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()

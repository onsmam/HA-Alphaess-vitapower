#!/usr/bin/env python3
"""Eenmalige, korte dispatch-test op een AlphaESS VitaPower.

Dit script SCHRIJFT naar de batterij: het laat de batterij kort laden of
ontladen via het dispatch-blok (0x0880) en zet daarna de dispatch weer stop.
Het schrijft alleen 0x0880-0x0889, en alleen na bevestiging.

Wat het controleert:
  - werkt schrijven met FC16 (meerdere registers)?
  - klopt het teken (onder 32000 = laden, boven = ontladen)?
  - leest de batterij de waarden terug zoals geschreven (SOC-schaal 0,4 %)?
  - overschrijft de AlphaESS-cloud de dispatch tijdens de test?
  - zet stoppen de batterij terug?

Veiligheid:
  - vermogen max 500 W, duur max 120 s;
  - de duur in de batterij zelf is test + 30 s: valt dit script weg,
    dan neemt de batterij daarna zelf de regie terug;
  - Ctrl+C of een fout stuurt altijd het stop-commando.

Gebruik (HA-integratie / YAML modbus-hub eerst uitzetten):
    python3 vitapower_dispatch_test.py --host 192.168.1.151
    python3 vitapower_dispatch_test.py --host 192.168.1.151 --power 300 --seconds 60
    python3 vitapower_dispatch_test.py --host 192.168.1.151 --discharge   # ontladen
"""

import argparse
import csv
import datetime as dt
import sys
import time

DISPATCH = 0x0880
OFFSET = 32000
SOC_STEP = 0.4  # % per eenheid in 0x0886
MAX_POWER = 500
MAX_SECONDS = 120
MARGIN_SECONDS = 30
# Wat de batterij zelf na een gestopte dispatch laat staan.
STOP_BLOCK = [0, 0, OFFSET, 0, OFFSET, 0, 0, 0, 90, 255]


def connect(host, port):
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from pymodbus.client.sync import ModbusTcpClient  # pymodbus 2.x
    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        sys.exit(
            f"Geen verbinding met {host}:{port}. Staat Home Assistant nog verbonden? "
            "De VitaPower staat maar een client toe."
        )
    return client


def _call(fn, *args, unit):
    for key in ("device_id", "slave", "unit"):  # pymodbus 3.x / 2.x
        try:
            return fn(*args, **{key: unit})
        except TypeError:
            continue
    raise RuntimeError("pymodbus-versie niet herkend")


def read(client, address, count, unit):
    rr = None
    for key in ("device_id", "slave", "unit"):
        try:
            rr = client.read_holding_registers(address, count=count, **{key: unit})
            break
        except TypeError:
            continue
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        raise RuntimeError(f"lezen 0x{address:04X} mislukt: {rr}")
    return list(rr.registers)


def write_block(client, values, unit):
    """FC16: alle registers vanaf 0x0880 in een keer."""
    rr = _call(client.write_registers, DISPATCH, values, unit=unit)
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        raise RuntimeError(f"schrijven 0x{DISPATCH:04X} mislukt: {rr}")


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def snapshot(client, unit):
    battery = read(client, 0x0100, 0x0127 - 0x0100, unit)
    inverter = read(client, 0x040C, 2, unit)
    dispatch = read(client, DISPATCH, 10, unit)
    settings = read(client, 0x0850, 6, unit)
    return {
        "soc": battery[0x02] / 10,
        "battery_v": battery[0x00] / 10,
        "battery_a": signed(battery[0x01], 16) / 10,
        "dc_w": signed(battery[0x26], 16),
        "ac_w": signed((inverter[0] << 16) | inverter[1], 32),
        "dispatch": dispatch,
        "dispatch_active": dispatch[0],
        "dispatch_w": ((dispatch[1] << 16) | dispatch[2]) - OFFSET,
        "dispatch_soc": dispatch[6] * SOC_STEP,
        "dispatch_s": (dispatch[7] << 16) | dispatch[8],
        "discharge_cutoff": settings[0],
        "charge_cutoff": settings[5],
    }


def line(s):
    return (
        f"SOC {s['soc']:5.1f} %  AC {s['ac_w']:6d} W  DC {s['dc_w']:6d} W  "
        f"I {s['battery_a']:6.1f} A  dispatch actief={s['dispatch_active']} "
        f"P={s['dispatch_w']:+d} W  doel={s['dispatch_soc']:.1f} %  duur={s['dispatch_s']} s"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="192.168.1.151")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=85)
    p.add_argument("--power", type=int, default=300, help=f"W, max {MAX_POWER}")
    p.add_argument("--seconds", type=int, default=120, help=f"max {MAX_SECONDS}")
    p.add_argument("--discharge", action="store_true", help="ontladen in plaats van laden")
    p.add_argument("--log", default=f"dispatch_test_{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
    args = p.parse_args()

    if not 50 <= args.power <= MAX_POWER:
        sys.exit(f"--power moet tussen 50 en {MAX_POWER} W liggen")
    if not 10 <= args.seconds <= MAX_SECONDS:
        sys.exit(f"--seconds moet tussen 10 en {MAX_SECONDS} liggen")

    client = connect(args.host, args.port)
    try:
        before = snapshot(client, args.unit)
        print("Nu:     ", line(before))
        print(f"Grenzen: ontladen {before['discharge_cutoff']} %, laden {before['charge_cutoff']} %")

        if before["dispatch_active"]:
            sys.exit(
                "\nDe dispatch is al actief: de AlphaESS-cloud stuurt de batterij nu. "
                "Een test zou overschreven worden. Zet in de app eerst een modus "
                "zonder cloud-sturing en probeer opnieuw."
            )
        if args.discharge:
            target = before["discharge_cutoff"]
            if before["soc"] < target + 5:
                sys.exit(f"\nSOC {before['soc']} % is te dicht bij de ontlaadgrens ({target} %).")
            power = args.power  # boven 32000 = ontladen
        else:
            target = before["charge_cutoff"]
            if before["soc"] > target - 3:
                sys.exit(f"\nSOC {before['soc']} % is te dicht bij de laadgrens ({target} %).")
            power = -args.power  # onder 32000 = laden

        soc_raw = round(target / SOC_STEP)
        duration = args.seconds + MARGIN_SECONDS
        block = [1, 0, OFFSET + power, 0, OFFSET, 2, soc_raw, 0, duration, 255]
        action = "ONTLADEN" if args.discharge else "LADEN"
        print(
            f"\nTest: {action} met {args.power} W, {args.seconds} s, doel-SOC {target} %."
            f"\nSchrijft 0x0880-0x0889 = {block}"
            f"\nStop daarna:            {STOP_BLOCK}"
        )
        if input("\nTyp 'ja' om te starten: ").strip().lower() != "ja":
            sys.exit("Afgebroken, er is niets geschreven.")

        with open(args.log, "w", newline="") as fh:
            log = csv.writer(fh)
            log.writerow(["tijd", "fase", "soc", "ac_w", "dc_w", "battery_a",
                          "dispatch_active", "dispatch_w", "dispatch_soc", "dispatch_s"])

            def record(phase, s):
                log.writerow([dt.datetime.now().isoformat(timespec="seconds"), phase, s["soc"],
                              s["ac_w"], s["dc_w"], s["battery_a"], s["dispatch_active"],
                              s["dispatch_w"], s["dispatch_soc"], s["dispatch_s"]])
                fh.flush()

            record("voor", before)
            ac_seen = []
            overwritten = False
            try:
                write_block(client, block, args.unit)
                print("\nGeschreven. TerugLezen:", read(client, DISPATCH, 10, args.unit))
                start = time.monotonic()
                while time.monotonic() - start < args.seconds:
                    time.sleep(5)
                    s = snapshot(client, args.unit)
                    record("test", s)
                    print(f"{time.monotonic() - start:5.0f} s ", line(s))
                    ac_seen.append(s["ac_w"])
                    if s["dispatch"] != block and not overwritten:
                        overwritten = True
                        print("  !! dispatch-blok wijkt af van wat geschreven is:", s["dispatch"])
            finally:
                write_block(client, STOP_BLOCK, args.unit)
                print("\nStop geschreven. Terugzien:", read(client, DISPATCH, 10, args.unit))

            for _ in range(3):
                time.sleep(5)
                s = snapshot(client, args.unit)
                record("na", s)
                print("na    ", line(s))

        settled = ac_seen[2:] or ac_seen
        mean = sum(settled) / len(settled) if settled else 0
        print("\n=== Resultaat ===")
        print(f"Gevraagd: {power:+d} W (+ = ontladen)   gemeten AC gemiddeld: {mean:+.0f} W")
        sign_ok = (mean < -50) if power < 0 else (mean > 50)
        print("Teken klopt:" , "ja" if sign_ok else "NEE / geen reactie")
        print("Blok overschreven tijdens test (cloud?):", "ja" if overwritten else "nee")
        print("Dispatch na stop actief:", s["dispatch_active"])
        print(f"Meetlog: {args.log}  - stuur dit bestand en deze uitvoer op.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Het stop-commando is dan al geschreven (finally hierboven).
        sys.exit("\nAfgebroken met Ctrl+C; de dispatch is gestopt.")

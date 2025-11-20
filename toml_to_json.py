#!/usr/bin/env python3
"""
Convert LOA_INPUT.toml → loa_configs_json/LOA.json (by default)
or: python toml_to_json.py input.toml output.json
"""

import json
import sys
from pathlib import Path

# ----- TOML loader -----
try:
    import tomllib            # Python 3.11+
except ImportError:
    import toml as tomllib    # pip install toml


def sector_from_string(s: str | None) -> str | None:
    """ Convert 'ed/HAM' → 'HAM' """
    if not s:
        return None
    return s.split("/")[-1].upper()


def convert(toml_data: dict) -> dict:
    agreements = toml_data.get("agreements", [])
    result: dict[str, dict] = {}

    for agr in agreements:
        from_sector = sector_from_string(agr.get("from_sector"))
        to_sector   = sector_from_string(agr.get("to_sector"))
        if not from_sector:
            continue

        ades = agr.get("ades")  # destinations
        adep = agr.get("adep")  # origins

        # Determine list type (destination or departure)
        if ades:
            list_name = "destinationLoas"
            field_name = "destinations"
            airports = ades
        elif adep:
            list_name = "departureLoas"
            field_name = "origins"
            airports = adep
        else:
            continue

        if from_sector not in result:
            result[from_sector] = {}
        if list_name not in result[from_sector]:
            result[from_sector][list_name] = []

        level = agr.get("level", 0)
        cop   = agr.get("cop")

        # ❌ SKIP IF: level == 0  OR  no cop defined
        if level == 0 or cop is None or str(cop).strip() == "":
            continue

        entry = {
            field_name: airports,
            "xfl": level,
            "nextSectors": [to_sector] if to_sector else [],
            "copText": cop,
            "waypoints": [cop]
        }

        result[from_sector][list_name].append(entry)

    return result


def main():
    # Defaults for GitHub: root/LOA_INPUT.toml → loa_configs_json/LOA.json
    input_path = Path("LOA_INPUT.toml")
    output_path = Path("loa_configs_json/LOA.json")

    # If arguments are given, override
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"ERROR: {input_path} not found.")
        return

    print(f"Reading {input_path} ...")
    toml_data = tomllib.loads(input_path.read_text())

    print("Converting...")
    loa_json = convert(toml_data)

    # Make sure target folder exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing output to {output_path} ...")
    output_path.write_text(json.dumps(loa_json, indent=4, ensure_ascii=False))

    print("Done!  ✔  JSON created.")


if __name__ == "__main__":
    main()

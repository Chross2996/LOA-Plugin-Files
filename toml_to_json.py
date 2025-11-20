#!/usr/bin/env python3
"""
Convert one or more LOA TOML files into a single LOA.json.

Usage examples:
    # Default (old behavior): use LOA_INPUT.toml → loa_configs_json/LOA.json
    python toml_to_json.py

    # Explicit single file:
    python toml_to_json.py path/to/file.toml loa_configs_json/LOA.json

    # Multiple TOML files merged into one LOA.json:
    python toml_to_json.py file1.toml file2.toml ... loa_configs_json/LOA.json

Rules:
- level == 0  OR  no cop defined -> skip that LOA.
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


def convert_one(toml_data: dict) -> dict:
    """Convert a single TOML dict into {sector: {destinationLoas, departureLoas}}."""
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


def merge_results(target: dict, addition: dict) -> None:
    """
    Merge 'addition' (from one TOML) into 'target' (global result).
    Keeps destinationLoas / departureLoas per sector and extends arrays.
    """
    for sector, sec_cfg in addition.items():
        if sector not in target:
            target[sector] = {}
        tgt_sec = target[sector]
        for key in ("destinationLoas", "departureLoas"):
            if key in sec_cfg:
                if key not in tgt_sec:
                    tgt_sec[key] = []
                tgt_sec[key].extend(sec_cfg[key])


def main():
    # Defaults: old behavior – single LOA_INPUT.toml -> loa_configs_json/LOA.json
    input_paths: list[Path]
    output_path: Path

    if len(sys.argv) == 1:
        input_paths = [Path("LOA_INPUT.toml")]
        output_path = Path("loa_configs_json/LOA.json")
    elif len(sys.argv) == 2:
        # One arg → input, default output
        input_paths = [Path(sys.argv[1])]
        output_path = Path("loa_configs_json/LOA.json")
    else:
        # Many args: all except last are TOML input files; last is output JSON
        *toml_args, out = sys.argv[1:]
        input_paths = [Path(p) for p in toml_args]
        output_path = Path(out)

    # Read all TOML files and merge
    global_result: dict[str, dict] = {}

    any_found = False
    for p in input_paths:
        if not p.exists():
            print(f"WARNING: {p} not found, skipping.")
            continue
        any_found = True
        print(f"Reading {p} ...")
        text = p.read_text(encoding="utf-8")
        toml_data = tomllib.loads(text)
        partial = convert_one(toml_data)
        merge_results(global_result, partial)

    if not any_found:
        print("ERROR: No valid TOML input files found. Nothing to do.")
        return

    # Make sure target folder exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing merged LOA JSON to {output_path} ...")
    output_path.write_text(json.dumps(global_result, indent=4, ensure_ascii=False), encoding="utf-8")

    print("Done! ✔ All TOMLs merged into LOA.json")


if __name__ == "__main__":
    main()

"""
generate_drop_sources.py

Generates data/drop_sources.json for the Drop Finder feature.

Sources:
  - Raidbots static data    → instance pool, item slot info (downloaded + cached locally)
  - Blizzard Game Data API  → item-per-boss loot tables (journal-instance / journal-encounter)

Usage:
    python scripts/generate_drop_sources.py
    python scripts/generate_drop_sources.py --creds blizz_api.json --output data/drop_sources.json
    python scripts/generate_drop_sources.py --refresh   # re-download cached Raidbots files

Requirements:
    pip install requests
"""

import argparse
import datetime
import json
import os
import sys
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CREDS = os.path.join(PROJECT_ROOT, "blizz_api.json")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "data", "drop_sources.json")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "_cache")

# ---------------------------------------------------------------------------
# Raidbots static URLs
# ---------------------------------------------------------------------------

RAIDBOTS_BASE = "https://www.raidbots.com/static/data/live"

# ---------------------------------------------------------------------------
# Blizzard API constants
# ---------------------------------------------------------------------------

BLIZZARD_TOKEN_URL = "https://oauth.battle.net/token"
BLIZZARD_API_BASE = "https://us.api.blizzard.com"
BLIZZARD_NAMESPACE = "static-us"
BLIZZARD_LOCALE = "en_US"

# ---------------------------------------------------------------------------
# Item-level tracks for Midnight Season 1 (hardcoded approximations).
# Update these values at the start of each new season.
# ---------------------------------------------------------------------------

ILVL_TRACKS = {
    "dungeon": [
        {"key": "champion", "label": "Champion (low keys)",  "ilvl": 250},
        {"key": "hero",     "label": "Hero (mid keys)",      "ilvl": 263},
        {"key": "myth",     "label": "Myth (high keys)",     "ilvl": 276},
    ],
    "raid": [
        {"key": "lfr",     "label": "LFR",     "ilvl": 246},
        {"key": "normal",  "label": "Normal",  "ilvl": 259},
        {"key": "heroic",  "label": "Heroic",  "ilvl": 272},
        {"key": "mythic",  "label": "Mythic",  "ilvl": 289},
    ],
}

# ---------------------------------------------------------------------------
# WoW inventory type -> SimC slot name
# ---------------------------------------------------------------------------

INVENTORY_TYPE_TO_SLOT = {
    1:  "head",
    2:  "neck",
    3:  "shoulder",
    5:  "chest",
    6:  "waist",
    7:  "legs",
    8:  "feet",
    9:  "wrist",
    10: "hands",
    11: "finger1",
    12: "trinket1",
    13: "main_hand",
    14: "off_hand",
    15: "ranged",
    16: "back",
    17: "main_hand",
    20: "chest",
    21: "main_hand",
    22: "off_hand",
    23: "off_hand",
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get_bytes(url: str, headers: dict = None, timeout: int = 60) -> bytes:
    if HAS_REQUESTS:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        r.raise_for_status()
        return r.content
    else:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()


def _http_get_json(url: str, headers: dict = None) -> dict:
    return json.loads(_http_get_bytes(url, headers=headers))


def _blizzard_get(endpoint: str, token: str) -> dict:
    url = (f"{BLIZZARD_API_BASE}{endpoint}"
           f"?namespace={BLIZZARD_NAMESPACE}&locale={BLIZZARD_LOCALE}")
    return _http_get_json(url, headers={"Authorization": f"Bearer {token}"})


# ---------------------------------------------------------------------------
# Raidbots static file cache
# ---------------------------------------------------------------------------

def _cache_path(filename: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, filename)


def _load_raidbots(filename: str, force_refresh: bool = False) -> bytes:
    path = _cache_path(filename)
    if os.path.exists(path) and not force_refresh:
        print(f"  [cache] {filename}")
        with open(path, "rb") as f:
            return f.read()
    url = f"{RAIDBOTS_BASE}/{filename}"
    print(f"  [download] {url}")
    data = _http_get_bytes(url)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  [saved] {len(data):,} bytes -> {path}")
    return data


# ---------------------------------------------------------------------------
# Blizzard OAuth
# ---------------------------------------------------------------------------

def get_token(client_id: str, client_secret: str) -> str:
    print("  Authenticating with Blizzard API...")
    if HAS_REQUESTS:
        r = requests.post(
            BLIZZARD_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=30,
        )
        r.raise_for_status()
        token = r.json()["access_token"]
    else:
        import urllib.request
        import base64
        cred_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        req = urllib.request.Request(
            BLIZZARD_TOKEN_URL,
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {cred_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            token = json.loads(resp.read())["access_token"]
    print("  Token obtained.")
    return token


# ---------------------------------------------------------------------------
# Instance / encounter discovery from Raidbots instances.json
# ---------------------------------------------------------------------------

def get_mplus_instance_ids(instances_meta: list) -> list:
    """Return journal-instance IDs for the current M+ dungeon pool."""
    for inst in instances_meta:
        if inst.get("type") == "mplus-chest":
            ids = [enc["id"] for enc in inst.get("encounters", [])]
            print(f"  M+ pool ({inst['name']}): {ids}")
            return ids
    print("  WARNING: No 'mplus-chest' instance found in instances.json")
    return []


def get_raid_instance_ids(instances_meta: list) -> list:
    """Return journal-instance IDs for current-season raids (id > 0, type='raid')."""
    raids = [
        i["id"]
        for i in instances_meta
        if i.get("type") == "raid" and isinstance(i.get("id"), int) and i["id"] > 0
    ]
    print(f"  Raid instances: {raids}")
    return raids


# ---------------------------------------------------------------------------
# Item metadata from Raidbots equippable-items-full.json
# ---------------------------------------------------------------------------

def build_item_lookup(raw_bytes: bytes) -> dict:
    """Return {item_id: {slot, class_mask}} for quick lookup."""
    items = json.loads(raw_bytes)
    lookup = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue
        inv_type = item.get("inventoryType", 0)
        slot = INVENTORY_TYPE_TO_SLOT.get(inv_type)
        if not slot:
            continue  # non-equippable or unrecognised slot type

        # class_mask from allowableClasses (list of class IDs, or absent = all classes)
        allowed = item.get("allowableClasses")
        if allowed and isinstance(allowed, list):
            mask = 0
            for cls_id in allowed:
                if isinstance(cls_id, int):
                    mask |= 1 << (cls_id - 1)
            class_mask = mask or -1
        else:
            class_mask = -1  # -1 means all classes

        lookup[item_id] = {"slot": slot, "class_mask": class_mask}

    print(f"  Item lookup: {len(lookup):,} equippable items")
    return lookup


# ---------------------------------------------------------------------------
# Blizzard journal API
# ---------------------------------------------------------------------------

def build_instance_data(
    instance_id: int,
    instance_type: str,
    token: str,
    item_lookup: dict,
) -> dict:
    """Fetch all encounters and their items for a journal-instance."""
    print(f"  Fetching journal-instance/{instance_id} ...")
    inst_data = _blizzard_get(f"/data/wow/journal-instance/{instance_id}", token)
    instance_name = inst_data.get("name", f"Instance {instance_id}")

    # 'encounters' is a direct list of {key, name, id} objects
    encounter_refs = inst_data.get("encounters", [])

    encounters = []
    for enc_ref in encounter_refs:
        enc_id = enc_ref["id"]
        enc_name = enc_ref.get("name", f"Encounter {enc_id}")
        print(f"    Boss: {enc_name} (id={enc_id})")
        time.sleep(0.15)

        try:
            enc_data = _blizzard_get(f"/data/wow/journal-encounter/{enc_id}", token)
        except Exception as e:
            print(f"      WARNING: Could not fetch encounter {enc_id}: {e}")
            continue

        raw_items = enc_data.get("items", [])
        items = []
        for item_ref in raw_items:
            item_info = item_ref.get("item", {})
            item_id = item_info.get("id")
            if not item_id:
                continue
            meta = item_lookup.get(item_id)
            if not meta:
                continue  # not in Raidbots equippable set (non-gear, or too new)
            items.append({
                "id": item_id,
                "name": item_info.get("name", f"Item {item_id}"),
                "slot": meta["slot"],
                "class_mask": meta["class_mask"],
            })

        time.sleep(0.1)

        if items:
            encounters.append({"id": enc_id, "name": enc_name, "items": items})
            print(f"      {len(items)} equippable items")
        else:
            print(f"      (no equippable items found in Raidbots data)")

    return {
        "id": instance_id,
        "name": instance_name,
        "type": instance_type,
        "encounters": encounters,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate data/drop_sources.json from Blizzard API + Raidbots data"
    )
    parser.add_argument("--creds", default=DEFAULT_CREDS,
                        help="Path to blizz_api.json (default: project root)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="Output path (default: data/drop_sources.json)")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-download of cached Raidbots files")
    args = parser.parse_args()

    if not HAS_REQUESTS:
        print("NOTE: 'requests' not installed. Using urllib (no retry on errors).")

    # Credentials
    if not os.path.exists(args.creds):
        print(f"ERROR: Credentials file not found: {args.creds}")
        sys.exit(1)
    with open(args.creds) as f:
        creds = json.load(f)
    client_id = creds["client-id"]
    client_secret = creds["client-secret"]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print("\n=== Step 1: Downloading Raidbots static files ===")
    instances_meta = json.loads(_load_raidbots("instances.json", args.refresh))
    print("  Loading equippable-items-full.json (large file, please wait)...")
    items_raw = _load_raidbots("equippable-items-full.json", args.refresh)
    item_lookup = build_item_lookup(items_raw)

    print("\n=== Step 2: Discovering current season instances ===")
    mplus_ids = get_mplus_instance_ids(instances_meta)
    raid_ids = get_raid_instance_ids(instances_meta)

    print("\n=== Step 3: Blizzard API authentication ===")
    token = get_token(client_id, client_secret)

    print("\n=== Step 4: Fetching M+ dungeon loot tables ===")
    all_instances = []
    for inst_id in mplus_ids:
        try:
            inst = build_instance_data(inst_id, "dungeon", token, item_lookup)
            all_instances.append(inst)
        except Exception as e:
            print(f"  ERROR fetching instance {inst_id}: {e}")
        time.sleep(0.3)

    print("\n=== Step 5: Fetching raid loot tables ===")
    for inst_id in raid_ids:
        try:
            inst = build_instance_data(inst_id, "raid", token, item_lookup)
            all_instances.append(inst)
        except Exception as e:
            print(f"  ERROR fetching raid {inst_id}: {e}")
        time.sleep(0.3)

    print("\n=== Step 6: Writing drop_sources.json ===")
    output = {
        "generated_at": datetime.date.today().isoformat(),
        "season": "Midnight Season 1",
        "instances": all_instances,
        "ilvl_tracks": ILVL_TRACKS,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_items = sum(
        len(enc.get("items", []))
        for inst in all_instances
        for enc in inst.get("encounters", [])
    )
    print(f"\nDone! -> {args.output}")
    print(f"  Instances : {len(all_instances)}")
    print(f"  Total items: {total_items}")


if __name__ == "__main__":
    main()

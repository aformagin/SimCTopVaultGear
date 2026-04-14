from simc_gv_generator import ParsedItem
from item_filters import is_item_armor_compatible, is_raw_item_armor_compatible


def _item(slot: str, item_id: int) -> ParsedItem:
    return ParsedItem(slot=slot, item_id=item_id, simc_string=f"{slot}=,id={item_id}")


def test_druid_accepts_leather_wrist():
    metadata = {
        249327: {"id": 249327, "itemClass": 4, "itemSubClass": 2},
    }
    assert is_item_armor_compatible(_item("wrist", 249327), "druid", metadata)


def test_druid_rejects_mail_wrist():
    metadata = {
        249304: {"id": 249304, "itemClass": 4, "itemSubClass": 3},
    }
    assert not is_item_armor_compatible(_item("wrist", 249304), "druid", metadata)


def test_druid_rejects_plate_hands():
    metadata = {
        264584: {"id": 264584, "itemClass": 4, "itemSubClass": 4},
    }
    assert not is_item_armor_compatible(_item("hands", 264584), "druid", metadata)


def test_mage_accepts_cloth_head():
    metadata = {
        12345: {"id": 12345, "itemClass": 4, "itemSubClass": 1},
    }
    assert is_item_armor_compatible(_item("head", 12345), "mage", metadata)


def test_mage_rejects_leather_head():
    metadata = {
        12345: {"id": 12345, "itemClass": 4, "itemSubClass": 2},
    }
    assert not is_item_armor_compatible(_item("head", 12345), "mage", metadata)


def test_non_armor_slots_are_not_filtered():
    metadata = {
        193708: {"id": 193708, "itemClass": 4, "itemSubClass": 4},
    }
    assert is_item_armor_compatible(_item("finger1", 193708), "druid", metadata)


def test_missing_metadata_defaults_to_allowed():
    assert is_item_armor_compatible(_item("wrist", 99999), "druid", {})


def test_raw_item_druid_rejects_mail_feet():
    metadata = {
        249320: {"id": 249320, "itemClass": 4, "itemSubClass": 3},
    }
    raw = {"id": 249320, "name": "Sabatons of Obscurement", "slot": "feet"}
    assert not is_raw_item_armor_compatible(raw, "druid", metadata)


def test_raw_item_hunter_accepts_mail_feet():
    metadata = {
        249320: {"id": 249320, "itemClass": 4, "itemSubClass": 3},
    }
    raw = {"id": 249320, "name": "Sabatons of Obscurement", "slot": "feet"}
    assert is_raw_item_armor_compatible(raw, "hunter", metadata)

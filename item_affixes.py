"""
Helpers for normalizing gem and enchant fields on SimC item strings.
"""

import re


AFFIX_FIELDS = ("enchant_id", "gem_id")


def get_item_param(simc_string: str, key: str):
    match = re.search(rf"(?:^|,){re.escape(key)}=([^,]+)", simc_string)
    if not match:
        return None
    return match.group(1)


def remove_item_param(simc_string: str, key: str) -> str:
    return re.sub(rf",{re.escape(key)}=[^,]+", "", simc_string)


def set_item_param(simc_string: str, key: str, value: str) -> str:
    cleaned = remove_item_param(simc_string, key)
    return f"{cleaned},{key}={value}"


def apply_reference_item_affixes(
    simc_string: str,
    reference_simc_string: str,
    fields=AFFIX_FIELDS,
) -> str:
    """Apply or clear affix fields so they match the reference item exactly."""
    updated = simc_string
    for field in fields:
        reference_value = get_item_param(reference_simc_string, field)
        if reference_value is None:
            updated = remove_item_param(updated, field)
        else:
            updated = set_item_param(updated, field, reference_value)
    return updated

"""SKU → lifecycle lookup.

Loads lifecycle_data.yaml once and exposes match(sku) -> Match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml


DATA_FILE = Path(__file__).parent / "lifecycle_data.yaml"


@dataclass(frozen=True)
class Match:
    sku: str
    kind: str  # "hardware" | "non_hardware" | "unknown" | "non_f5"
    family_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    end_of_sale: Optional[date] = None
    end_of_software_dev: Optional[date] = None
    end_of_technical_support: Optional[date] = None
    end_of_rma: Optional[date] = None
    category: Optional[str] = None
    note: Optional[str] = None


def _normalize(sku: object) -> str:
    if sku is None:
        return ""
    s = str(sku).strip().upper()
    # collapse internal whitespace, keep dashes
    s = re.sub(r"\s+", "", s)
    return s


@lru_cache(maxsize=1)
def _load():
    with DATA_FILE.open() as f:
        raw = yaml.safe_load(f)
    families = []
    for fam in raw["families"]:
        compiled = [re.compile(p, re.IGNORECASE) for p in fam["sku_patterns"]]
        families.append((compiled, fam))
    non_hw = []
    for group in raw.get("non_hardware_patterns", []):
        compiled = [re.compile(p, re.IGNORECASE) for p in group["patterns"]]
        non_hw.append((compiled, group))
    return families, non_hw, raw.get("data_revision")


def data_revision() -> Optional[str]:
    _, _, rev = _load()
    return str(rev) if rev else None


def match(raw_sku: object) -> Match:
    sku = _normalize(raw_sku)
    if not sku:
        return Match(sku="", kind="unknown")

    families, non_hw, _ = _load()

    for compiled, fam in families:
        if any(p.match(sku) for p in compiled):
            return Match(
                sku=sku,
                kind="hardware",
                family_id=fam["family_id"],
                display_name=fam["display_name"],
                status=fam["status"],
                end_of_sale=fam.get("end_of_sale"),
                end_of_software_dev=fam.get("end_of_software_dev"),
                end_of_technical_support=fam.get("end_of_technical_support"),
                end_of_rma=fam.get("end_of_rma"),
                note=fam.get("notes"),
            )

    for compiled, group in non_hw:
        if any(p.match(sku) for p in compiled):
            return Match(
                sku=sku,
                kind="non_hardware",
                category=group["category"],
                note=group["note"],
            )

    if sku.startswith("F5-") or sku.startswith("F5 "):
        return Match(sku=sku, kind="unknown")

    return Match(sku=sku, kind="non_f5")

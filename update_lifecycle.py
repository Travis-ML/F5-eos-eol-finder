#!/usr/bin/env python3
"""Lifecycle data maintenance CLI.

Subcommands:
  validate         Schema, regex, and date checks on lifecycle_data.yaml
  test             Run the matcher against the SKU fixture corpus
  diff             Show what changed in lifecycle_data.yaml since git HEAD
  bump-revision    Set data_revision to today's date if YAML changed
  check            validate + test (use as a pre-commit hook)

Exit code is non-zero if any check fails. No network calls.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "lifecycle_data.yaml"
FIXTURE_FILE = ROOT / "fixtures" / "sku_corpus.yaml"

VALID_STATUSES = {
    "regular",
    "regular_no_eos",
    "eos_announced",
    "eosd",
    "eots",
}

REQUIRED_FAMILY_FIELDS = {
    "family_id",
    "display_name",
    "status",
    "sku_patterns",
}

DATE_FIELDS = (
    "end_of_sale",
    "end_of_software_dev",
    "end_of_technical_support",
    "end_of_rma",
)


# ---------- output helpers --------------------------------------------------

USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def red(t: str) -> str:
    return _c("31", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def bold(t: str) -> str:
    return _c("1", t)


# ---------- loading ---------------------------------------------------------


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def load_yaml_text(text: str) -> dict:
    return yaml.safe_load(StringIO(text))


# ---------- validate --------------------------------------------------------


def cmd_validate(_args) -> int:
    data = load_yaml(DATA_FILE)
    errors: list[str] = []
    warnings: list[str] = []

    rev = data.get("data_revision")
    if not isinstance(rev, date):
        errors.append(
            f"data_revision must be an ISO date (YYYY-MM-DD), got {rev!r}"
        )

    families = data.get("families") or []
    if not isinstance(families, list) or not families:
        errors.append("families: must be a non-empty list")
        families = []

    seen_ids: set[str] = set()
    seen_patterns: dict[str, str] = {}  # pattern -> family_id

    for i, fam in enumerate(families):
        loc = f"families[{i}]"
        if not isinstance(fam, dict):
            errors.append(f"{loc}: must be a mapping")
            continue

        missing = REQUIRED_FAMILY_FIELDS - set(fam.keys())
        if missing:
            errors.append(f"{loc}: missing required fields: {sorted(missing)}")
            continue

        fid = fam["family_id"]
        loc = f"families[{i}] ({fid})"

        if fid in seen_ids:
            errors.append(f"{loc}: duplicate family_id")
        seen_ids.add(fid)

        status = fam["status"]
        if status not in VALID_STATUSES:
            errors.append(
                f"{loc}: invalid status {status!r}; must be one of "
                f"{sorted(VALID_STATUSES)}"
            )

        for fname in DATE_FIELDS:
            v = fam.get(fname)
            if v is None:
                continue
            if not isinstance(v, date):
                errors.append(
                    f"{loc}: {fname} must be an ISO date or null, got {v!r}"
                )

        # status / dates consistency
        if status in {"eos_announced", "eosd", "eots"} and not fam.get("end_of_sale"):
            warnings.append(
                f"{loc}: status is {status!r} but end_of_sale is null"
            )
        if status == "regular_no_eos" and any(fam.get(f) for f in DATE_FIELDS):
            warnings.append(
                f"{loc}: status is regular_no_eos but has dates set; "
                "did you mean status: eos_announced or eosd?"
            )

        # date ordering
        eos = fam.get("end_of_sale")
        eosd = fam.get("end_of_software_dev")
        eots = fam.get("end_of_technical_support")
        if eos and eosd and eosd < eos:
            errors.append(f"{loc}: end_of_software_dev ({eosd}) is before end_of_sale ({eos})")
        if eosd and eots and eots < eosd:
            errors.append(f"{loc}: end_of_technical_support ({eots}) is before end_of_software_dev ({eosd})")

        patterns = fam.get("sku_patterns") or []
        if not isinstance(patterns, list) or not patterns:
            errors.append(f"{loc}: sku_patterns must be a non-empty list")
            continue
        for p in patterns:
            if not isinstance(p, str):
                errors.append(f"{loc}: sku_pattern must be a string, got {p!r}")
                continue
            try:
                re.compile(p, re.IGNORECASE)
            except re.error as e:
                errors.append(f"{loc}: invalid regex {p!r}: {e}")
                continue
            if p in seen_patterns and seen_patterns[p] != fid:
                errors.append(
                    f"{loc}: pattern {p!r} also defined in family "
                    f"{seen_patterns[p]!r}"
                )
            seen_patterns[p] = fid

    # non_hardware patterns
    nh = data.get("non_hardware_patterns") or []
    if not isinstance(nh, list):
        errors.append("non_hardware_patterns must be a list")
        nh = []
    for i, group in enumerate(nh):
        loc = f"non_hardware_patterns[{i}]"
        if not isinstance(group, dict):
            errors.append(f"{loc}: must be a mapping")
            continue
        for req in ("category", "note", "patterns"):
            if req not in group:
                errors.append(f"{loc}: missing required field {req!r}")
        for p in (group.get("patterns") or []):
            try:
                re.compile(p, re.IGNORECASE)
            except re.error as e:
                errors.append(f"{loc} ({group.get('category')}): invalid regex {p!r}: {e}")

    for w in warnings:
        print(f"{yellow('warning:')} {w}")
    for e in errors:
        print(f"{red('error:')} {e}")

    if errors:
        print(red(f"\n{len(errors)} error(s), {len(warnings)} warning(s)"))
        return 1
    print(green(
        f"OK: {len(families)} families, "
        f"{len(seen_patterns)} hardware patterns, "
        f"{len(nh)} non-hardware groups"
        + (f" ({len(warnings)} warning(s))" if warnings else "")
    ))
    return 0


# ---------- test ------------------------------------------------------------


def cmd_test(_args) -> int:
    # Import here so a broken matcher doesn't prevent `validate` from running.
    sys.path.insert(0, str(ROOT))
    from matcher import match  # noqa: E402

    fixtures = load_yaml(FIXTURE_FILE)
    failures: list[str] = []
    total = 0

    for fid, skus in (fixtures.get("hardware") or {}).items():
        for sku in skus:
            total += 1
            m = match(sku)
            if m.kind != "hardware" or m.family_id != fid:
                failures.append(
                    f"  {sku!r}: expected hardware/{fid}, got "
                    f"{m.kind}/{m.family_id}"
                )

    for cat, skus in (fixtures.get("non_hardware") or {}).items():
        for sku in skus:
            total += 1
            m = match(sku)
            if m.kind != "non_hardware" or m.category != cat:
                failures.append(
                    f"  {sku!r}: expected non_hardware/{cat!r}, got "
                    f"{m.kind}/{m.category!r}"
                )

    for sku in (fixtures.get("unknown_f5") or []):
        total += 1
        m = match(sku)
        if m.kind != "unknown":
            failures.append(
                f"  {sku!r}: expected unknown, got {m.kind}/{m.family_id}"
            )

    for sku in (fixtures.get("non_f5") or []):
        total += 1
        m = match(sku)
        if m.kind != "non_f5":
            failures.append(
                f"  {sku!r}: expected non_f5, got {m.kind}/{m.family_id}"
            )

    if failures:
        print(red(f"FAIL ({len(failures)} of {total}):"))
        for f in failures:
            print(red(f))
        return 1
    print(green(f"OK: {total} fixture SKUs all classified correctly"))
    return 0


# ---------- diff ------------------------------------------------------------


def _git_show_head() -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "show", "HEAD:lifecycle_data.yaml"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            return None
        return r.stdout
    except FileNotFoundError:
        return None


def _families_by_id(data: dict) -> dict[str, dict]:
    return {f["family_id"]: f for f in (data.get("families") or [])}


def _format_date(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def cmd_diff(_args) -> int:
    head_text = _git_show_head()
    if head_text is None:
        print(yellow(
            "no git HEAD revision of lifecycle_data.yaml found "
            "(not a git repo, or file is new)"
        ))
        return 0

    head = load_yaml_text(head_text)
    cur = load_yaml(DATA_FILE)

    head_fams = _families_by_id(head)
    cur_fams = _families_by_id(cur)

    head_rev = head.get("data_revision")
    cur_rev = cur.get("data_revision")
    if head_rev != cur_rev:
        print(bold(f"data_revision: {head_rev} → {cur_rev}"))

    added = sorted(set(cur_fams) - set(head_fams))
    removed = sorted(set(head_fams) - set(cur_fams))
    common = sorted(set(cur_fams) & set(head_fams))

    if added:
        print(green(f"\nAdded families ({len(added)}):"))
        for fid in added:
            print(green(f"  + {fid}  {cur_fams[fid].get('display_name')}"))

    if removed:
        print(red(f"\nRemoved families ({len(removed)}):"))
        for fid in removed:
            print(red(f"  - {fid}  {head_fams[fid].get('display_name')}"))

    changed_count = 0
    for fid in common:
        h = head_fams[fid]
        c = cur_fams[fid]
        changes: list[str] = []

        if h.get("status") != c.get("status"):
            changes.append(f"    status: {h.get('status')} → {c.get('status')}")

        for f in DATE_FIELDS:
            if h.get(f) != c.get(f):
                changes.append(
                    f"    {f}: {_format_date(h.get(f))} → {_format_date(c.get(f))}"
                )

        if (h.get("sku_patterns") or []) != (c.get("sku_patterns") or []):
            changes.append("    sku_patterns: changed")

        if h.get("display_name") != c.get("display_name"):
            changes.append(
                f"    display_name: {h.get('display_name')!r} → {c.get('display_name')!r}"
            )

        if changes:
            changed_count += 1
            print(yellow(f"\nChanged: {fid}  {c.get('display_name')}"))
            for line in changes:
                print(line)

    if not (added or removed or changed_count or head_rev != cur_rev):
        print(green("No changes since HEAD."))

    return 0


# ---------- bump-revision ---------------------------------------------------


def _yaml_text_with_revision(text: str, new_rev: date) -> str:
    """Rewrite the data_revision line in YAML text without re-serializing
    the whole file (preserves comments, formatting, key order)."""
    pattern = re.compile(r"^(data_revision:\s*).+$", re.MULTILINE)
    if not pattern.search(text):
        raise ValueError("data_revision: line not found in YAML")
    return pattern.sub(rf"\g<1>{new_rev.isoformat()}", text, count=1)


def _content_changed_vs_head() -> bool:
    head = _git_show_head()
    if head is None:
        return True  # no HEAD = treat as changed
    cur = DATA_FILE.read_text()
    # ignore the data_revision line itself when deciding "did content change"
    strip = lambda s: re.sub(  # noqa: E731
        r"^data_revision:.*$", "", s, count=1, flags=re.MULTILINE
    )
    return strip(head).strip() != strip(cur).strip()


def cmd_bump_revision(args) -> int:
    today = date.today()
    text = DATA_FILE.read_text()

    cur = load_yaml(DATA_FILE)
    cur_rev = cur.get("data_revision")

    if not _content_changed_vs_head():
        print(green(f"No content changes vs HEAD; data_revision left at {cur_rev}"))
        return 0

    if cur_rev == today and not args.force:
        print(green(f"data_revision already set to today ({today})"))
        return 0

    new_text = _yaml_text_with_revision(text, today)
    DATA_FILE.write_text(new_text)
    print(green(f"data_revision: {cur_rev} → {today}"))
    return 0


# ---------- check -----------------------------------------------------------


def cmd_check(args) -> int:
    print(bold("validate:"))
    rc = cmd_validate(args)
    if rc != 0:
        # Skip test: a broken YAML will just make the matcher crash on load,
        # which is noise on top of the real validate errors.
        print(yellow("\ntest: skipped (validate failed; fix the errors above first)"))
        return rc
    print(bold("\ntest:"))
    return cmd_test(args)


# ---------- main ------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(
        prog="update_lifecycle.py",
        description="Maintain lifecycle_data.yaml safely.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="Schema/regex/date checks").set_defaults(func=cmd_validate)
    sub.add_parser("test", help="Run matcher against fixture SKU corpus").set_defaults(func=cmd_test)
    sub.add_parser("diff", help="Show changes vs git HEAD").set_defaults(func=cmd_diff)

    bp = sub.add_parser("bump-revision", help="Set data_revision to today if YAML changed")
    bp.add_argument("--force", action="store_true", help="Bump even if already today's date")
    bp.set_defaults(func=cmd_bump_revision)

    sub.add_parser("check", help="validate + test (suitable for pre-commit)").set_defaults(func=cmd_check)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

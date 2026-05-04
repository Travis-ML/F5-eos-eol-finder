# F5 EoS / EoL Finder

Upload an Excel sales document, BOM, or inventory and get the same file back
with **End-of-Sale**, **End-of-Software-Development**, and
**End-of-Technical-Support** dates filled in for every F5 hardware line item.

Built for sales / account teams who need to flag aging F5 gear in a customer
inventory or quote without combing through F5's K-articles by hand.

---

## Quick start

You need **Python 3.10 or newer**. That's it.

### macOS / Linux

```bash
git clone https://github.com/<your-org>/F5-eosfinder.git
cd F5-eosfinder
./run.sh
```

### Windows

```bat
git clone https://github.com/<your-org>/F5-eosfinder.git
cd F5-eosfinder
run.bat
```

The first run sets up a Python virtual environment and installs dependencies
(takes ~10 seconds). Every later run starts instantly. Your browser will open
to `http://127.0.0.1:5000` — drag in your `.xlsx`, click **Annotate &
download**, and the annotated copy lands in your Downloads folder.

To stop the server: press **Ctrl+C** in the terminal window.

---

## What you get back

For every row containing an F5 SKU, seven new columns are appended to the
right of your existing data:

| Column | Example |
|---|---|
| F5 EoL — Family / Category | `BIG-IP iSeries i4600` |
| Status | `Past End of Software Dev` |
| End of Sale | `2024-01-01` |
| End of Software Dev | `2026-01-01` |
| End of Technical Support | `2031-01-01` |
| End of RMA | `2031-01-01` |
| Notes | _(any extra context from the lifecycle DB)_ |

Rows are color-coded by status (red = past EoSD, amber = EoS announced,
green = regular support).

A **F5 EoL Summary** sheet is inserted at the front with row counts by
status, a list of any unrecognized F5 SKUs that need manual review, and the
revision date of the lifecycle data the run was based on.

### What it handles intelligently

- **BOM with both `Part Number` and `Covered Product` columns** — picks the
  hardware SKU (the covered product) over the service SKU (e.g.
  `F5-SVC-BIG-PRE-L1-3`) so you see the EoL of the actual gear under
  contract.
- **Service / VE / BIG-IQ / ELA / consulting lines** — tagged with their
  category but not given fake EoL dates (they don't have hardware EoL of
  their own).
- **Non-F5 line items** — left alone.
- **Unknown F5 SKUs** — flagged in the summary sheet so you know what to
  look up manually.

### What it doesn't do

- **PDF input** — Excel only for now.
- **Per-version software EoL** — VE / BIG-IQ lifecycle is governed by
  software version, not hardware family, and is out of scope.
- **Live lookups** — dates come from a curated local database. See below
  for how to keep it current.

---

## Keeping the lifecycle data current

Dates live in [`lifecycle_data.yaml`](lifecycle_data.yaml). The source of
truth is **F5 K4309: Hardware Product Lifecycle Support Policy** at
<https://my.f5.com/manage/s/article/K4309>.

When F5 updates K4309 (typically a few times a year as new EoS announcements
land):

1. Open [`lifecycle_data.yaml`](lifecycle_data.yaml) in any text editor.
2. Update the dates for affected families, or copy/paste an existing entry
   to add a new family.
3. Bump `data_revision:` at the top to today's date.
4. Commit and push.

Each entry has the same shape:

```yaml
- family_id: bigip-i4600
  display_name: BIG-IP iSeries i4600
  hw_code: C115
  status: eosd                       # regular | regular_no_eos | eos_announced | eosd | eots
  end_of_sale: 2024-01-01
  end_of_software_dev: 2026-01-01
  end_of_technical_support: 2031-01-01
  end_of_rma: 2031-01-01
  sku_patterns:
    - '^F5-BIG-.*-I4600(-.*)?$'
    - '^F5-BIG-I4600(-.*)?$'
```

Always **verify against K4309** before relying on dates in a customer
deliverable — the local DB is a convenience cache, not authoritative.

---

## ⚠️ Customer data — do NOT commit

Real BOMs, RFQs, and inventories contain serial numbers, project codenames,
and customer/contact info. The included [`.gitignore`](.gitignore) excludes
**all** `.xlsx` / `.xlsm` files by default. Do not override that exclusion
unless you've confirmed the file is fully redacted.

If you want to ship a sample for testing or screenshots, put a fully sanitized
file in a `sample_data/` folder — the gitignore allows that path explicitly.

---

## Project layout

```
F5-eosfinder/
├── app.py                 Flask web app (one upload endpoint)
├── matcher.py             SKU normalization + lifecycle lookup
├── annotator.py           Excel walker that writes the new columns
├── lifecycle_data.yaml    The lifecycle database — edit this to update dates
├── templates/
│   └── index.html         Upload form
├── requirements.txt       Python deps (Flask, openpyxl, PyYAML)
├── run.sh                 Mac / Linux launcher
├── run.bat                Windows launcher
└── README.md
```

---

## Troubleshooting

**`python3: command not found`**
Install Python 3.10+ from <https://www.python.org/downloads/>. On Windows,
make sure to check "Add Python to PATH" during install.

**Browser doesn't open automatically**
Just visit <http://127.0.0.1:5000> manually.

**Port 5000 already in use** (common on macOS — AirPlay Receiver uses it)
Edit the last line of `app.py` and change `port=5000` to `port=5050` (or
any free port), then update the URL in your browser.

**An F5 SKU comes back as "Unknown F5 SKU — needs review"**
The SKU isn't in `lifecycle_data.yaml` yet. Look it up in K4309 and add a
new family entry, or add a new pattern to an existing family if it's a
variant of one already there.

---

## License

MIT — see [LICENSE](LICENSE).

Lifecycle data is sourced from F5's published K4309 article. F5 and BIG-IP
are trademarks of F5, Inc. This project is not affiliated with F5.

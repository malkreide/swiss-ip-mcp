#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate finding docs (template-conformant) from verification-results.json.

Reproducible alternative to hand-writing 26 finding files. Reads the
canonical results + the check catalog frontmatter (title, pdf_ref,
effort) and emits findings/<CHECK-ID>-<slug>.md for every fail/partial.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AUDIT_DIR = Path(sys.argv[1])
CATALOG = Path(sys.argv[2])
SERVER = "swiss-ip-mcp"
AUDIT_DATE = "2026-06-02"
AUDITOR = "mcp-audit-skill v1.0.0 (automatisiert)"

results = json.loads((AUDIT_DIR / "verification-results.json").read_text("utf-8"))["results"]
out = AUDIT_DIR / "findings"
out.mkdir(exist_ok=True)


def meta(check_id: str) -> dict:
    t = (CATALOG / f"{check_id}.md").read_text("utf-8")
    fm = t.split("---")[1]
    title = re.search(r'title:\s*"?(.*?)"?\n', fm).group(1)
    pdf = re.search(r'pdf_ref:\s*"?(.*?)"?\n', fm)
    em = re.search(r"## Effort\s*\n+\s*([SMLX]+)", t)
    return {
        "title": title,
        "pdf_ref": pdf.group(1) if pdf else "—",
        "effort": em.group(1) if em else "M",
    }


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48]


written = []
for cid, r in results.items():
    if r["status"] not in ("fail", "partial"):
        continue
    m = meta(cid)
    ev = "\n".join(f"- {e}" for e in r["evidence"]) or "- (kein bestaetigendes Positiv-Evidence; Check-Kriterien nicht erfuellt)"
    gaps = "\n".join(f"- {g}" for g in r["gaps"]) or "- —"
    body = f"""## Finding: {cid} — {m['title']}

| Feld | Wert |
|---|---|
| **Severity** | {r['severity']} |
| **Status** | open |
| **Server** | `{SERVER}` |
| **Check-Reference** | `{cid}` |
| **PDF-Reference** | {m['pdf_ref']} |
| **Audit-Datum** | {AUDIT_DATE} |
| **Auditor** | {AUDITOR} |
| **Check-Status** | {r['status']} |

### Observed Behavior

{ev}

### Gaps / Expected Behavior

Der Best-Practice-Katalog ({cid}) verlangt die Behebung folgender Luecken:

{gaps}

### Risk Description

Siehe Severity `{r['severity']}`. Details und Remediation im Check-Katalog
`checks/{cid}.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

{m['effort']}

### Verification After Fix

- Re-Audit dieses Checks ({cid}) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)
"""
    fname = f"{cid}-{slug(m['title'])}.md"
    (out / fname).write_text(body, "utf-8")
    written.append(fname)

print(f"wrote {len(written)} findings")
for w in sorted(written):
    print(" ", w)

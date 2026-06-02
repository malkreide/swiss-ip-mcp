## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-ip-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |
| **Check-Status** | partial |

### Observed Behavior

- Pydantic >= 2.0 in dependencies; Input-Models exzellent typisiert
- StrEnum ResponseFormat fuer enumerable Werte (server.py:322-324)

### Gaps / Expected Behavior

Der Best-Practice-Katalog (SDK-002) verlangt die Behebung folgender Luecken:

- Tools geben rohen json.dumps-String zurueck (-> str), keine strukturierten BaseModel/TypedDict/Dataclass-Return-Typen (z.B. server.py:584)
- Response-Envelope (total/count/items/next_page_token) ohne source/provenance-Felder

### Risk Description

Siehe Severity `medium`. Details und Remediation im Check-Katalog
`checks/SDK-002.md` (Sektionen *Risk* / *Remediation* / *Common Failures*).

### Effort Estimate

S

### Verification After Fix

- Re-Audit dieses Checks (SDK-002) gegen denselben Katalog-Hash
- Status muss auf `pass` wechseln (alle Gaps geschlossen)

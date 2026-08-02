# License Compliance Checklist

This document tracks license compliance for all external dependencies
referenced by agent-governance.

---

## Compliance Status

| Component | License | Compliant? | Action Required |
|-----------|---------|:----------:|-----------------|
| VeritasBench (design) | Apache 2.0 | ✅ | None — design reference only |
| HUMMBL (dataset) | CC-BY-4.0 + eval-only | ✅ | Declared in ACKNOWLEDGMENTS.md |
| HUMMBL (code) | No LICENSE file | ✅ | Design reference only, no code copied |
| A2A Protocol (design) | Apache 2.0 | ✅ | None — design reference only |
| SessionBound (design) | Apache 2.0 | ✅ | None — design reference only |
| CSL-Core (design) | Apache 2.0 | ✅ | None — design reference only |
| MSFT Toolkit (design) | MIT | ✅ | None — design reference only |
| Warden (design) | TBD | ⚠️ | Confirm license before code reuse |
| Scorecard (design) | TBD | ⚠️ | Confirm license before code reuse |
| Clearstone SDK (design) | TBD | ⚠️ | Confirm license before code reuse |
| bounce12340/agent-governance | No LICENSE | ⚠️ | Design reference only, no code copied |

---

## Action Items

- [ ] Confirm Warden license (github.com/WhiteFinSec/warden)
- [ ] Confirm Scorecard license (github.com/Equilateral-AI/agent-governance-scorecard)
- [ ] Confirm Clearstone SDK license (github.com/Sancauid/clearstone-sdk)
- [x] ACKNOWLEDGMENTS.md created with full attribution
- [x] HUMMBL dataset: evaluation-only restriction documented
- [x] No code copied from unlicensed repositories

---

## MIT + Apache 2.0 Compatibility

| Scenario | Status |
|----------|:------:|
| MIT project referencing Apache 2.0 code | ✅ Compatible |
| MIT project containing Apache 2.0 fragments | ✅ Compatible (retain copyright notice) |
| MIT project modifying Apache 2.0 code | ✅ Compatible (retain copyright + disclaimer) |

---

*Last updated: 2026-08-01*

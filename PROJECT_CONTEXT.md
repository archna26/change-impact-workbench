# PROJECT_CONTEXT.md — Change Impact Workbench
# Legacy Retail Co — IBM Bob 2.0 Hackathon

## Approved Scope

Build a reusable **Change Impact Workbench** that traces evidence-backed
dependencies across legacy source files and produces a three-tier impact
report (Confirmed / Needs Review / Unknown) for any starting artifact.

Demonstrate on two legacy stacks:
- **IBM i** — Legacy Retail Co fictional system (DDS, RPG ILE, CL)
- **COBOL** — fictional billing module (copybooks, COBOL programs)

## Repository: Legacy Retail Co (folder: BOB_HT/)

Fictional, representative source. Files are synthetic — never compiled
or run on IBM i or any COBOL platform. Evidence is extracted from them
by the engine, not invented.

## Change Requests

| ID  | Artifact       | Language | Pattern      | Status        |
|-----|----------------|----------|--------------|---------------|
| CR-1 | ORDSTS field  | IBM i    | Field fan-out | Implemented + tested |
| CR-2 | PRICECALC pgm | IBM i    | Program fan-in | Simulation + boundary test |
| CR-3 | BILL-RATE field| COBOL   | COPY fan-out | Implemented + tested |

## Business Invariants (CR-1)

- INV-1: Held orders (H) must NOT appear on warehouse pick list
- INV-2: Commission paid only when ORDSTS = 'P' (Picking)
- INV-3: ALLOC_ORDERS uses = 'O' — safe throughout (positive predicate)

## Status Transition Table (ORDSTS)

| Status | Code | Valid next |
|--------|------|-----------|
| Open     | O | H, P, X |
| Hold     | H | O, X    |
| Picking  | P | C       |
| Closed   | C | terminal |
| Cancelled| X | terminal |

## Engine Capabilities

Detects: DDS field definitions, COBOL copybook field definitions,
RPG Dcl-F file opens, RPG ExtPgm call prototypes, CL CALL PGM(),
SQL WHERE predicate lines, COBOL COPY members, COBOL CALL literals,
RPG LHS assignment (WRITES_FIELD), COBOL MOVE TO (WRITES_FIELD),
CL/COBOL indirect callers (one-hop).

Does NOT detect: dynamic calls, binding directory members, PERFORM THROUGH,
RPG locally-renamed field variables, semantic predicate meaning.

## Test Status

| File | Tests | Status |
|------|-------|--------|
| test_baseline.py | 13 | All PASS |
| test_incomplete_change.py | 2 | Both FAIL (intentional — demonstrate hidden deps) |
| test_complete_fix.py | 9 | All PASS |
| test_cobol_billing.py | 7 | All PASS |
| **Total** | **31** | **29 pass, 2 intentional fail** |

## Key Commands

```bash
python sim/ciw_engine.py --catalog
python sim/ciw_engine.py --artifact ORDSTS --type field --lang ibmi
python sim/ciw_engine.py --artifact PRICECALC --type program --lang ibmi
python sim/ciw_engine.py --artifact BILL-RATE --type field --lang cobol
python -m pytest tests/ -v
```

## Answer Key Location

`tests/answer_key.json` — written before engine ran. Do not modify.
Engine output is scored against this file, not against itself.

## Decisions Log

- ORDENTRY2 removed; replaced by INVPRICJOB as the realistic PRICECALC batch caller
- STMTJOB now calls INVPRICJOB (not ORDENTRY2) — indirect PRICECALC dependency is genuine
- `possible` tier renamed to `needs-review` to clarify that confirmed = source reference only
- WRITES_FIELD / READS_FIELD / SQL_PREDICATE / DIRECT_CALLER / INDIRECT_CALLER / COPY_MEMBER / COBOL_CALL labels replace generic CALLS_PGM/READS_FIELD
- COBOL adapter added as separate indexer functions — no IBM i-specific code in COBOL path

## Next Actions

- **[MANUAL] Capture Bob session screenshots** — click the task header in the Bob IDE
  for each task session, screenshot the consumption summary popup, save as PNG to
  `bob_sessions/` using the naming convention in `bob_sessions/README.md`
- Run `python sim/ciw_engine.py --artifact PRICECALC --type program --lang ibmi`
  to demonstrate CR-2 program fan-in traversal in the demo video
- Record three-minute demo video per README timeline
- Commit and push `bob_sessions/` PNG files before 27 Sep 2026 20:30 IST

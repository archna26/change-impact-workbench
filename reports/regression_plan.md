# Regression Plan

**Artifact:** `BILL-RATE` | **Type:** field | **Lang:** cobol

> Tests run in the Python simulation harness (sim/retailco_sim.py for IBM i (Legacy Retail Co),
> sim/billing_sim.py for COBOL). These simulate the predicate and business-rule
> logic from the representative source. No IBM i or COBOL platform is involved.

## Test Cases

| # | Test Name | Consumer | Condition | Expected Result | Pass Criteria |
|---|-----------|----------|-----------|-----------------|---------------|
| 1 | test_bilprint_copy | BILPRINT | Field changed in copybook | All COPY users handle new definition | Assert each consumer produces correct output |
| 2 | test_calcbill_copy | CALCBILL | Field changed in copybook | All COPY users handle new definition | Assert each consumer produces correct output |

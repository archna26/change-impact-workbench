# Change Checklist

**Artifact:** `BILL-RATE` | **Type:** field | **Lang:** cobol

| # | Artifact | Relationship | Action Required | Tier | Owner |
|---|----------|--------------|-----------------|------|-------|
| 1 | `BILREC.BILL-RATE` | DEFINES | Update definition and document business rule for new value | confirmed | Developer |
| 2 | `BILPRINT` | READS_FIELD | Verify read usage handles new value without error | confirmed | Developer |
| 3 | `BILPRINT` | COPY_MEMBER | Verify all COPY usages handle field change; regression test each program | confirmed | Developer |
| 4 | `CALCBILL` | READS_FIELD | Verify read usage handles new value without error | confirmed | Developer |
| 5 | `CALCBILL` | COPY_MEMBER | Verify all COPY usages handle field change; regression test each program | confirmed | Developer |

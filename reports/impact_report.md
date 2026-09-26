# Change Impact Report

> **Source files:** Fictional representative source files (IBM i DDS/RPG ILE/CL;
> COBOL copybooks and programs). Catalog evidence is genuinely extracted from
> those files, but the files are synthetic — never compiled or run on any platform.
>
> **Confirmed** = token or structural pattern found at the cited path and line.
> This is a *source reference* claim. Behavioral impact is NOT claimed.
>
> **Needs Review** = predicate, write, or call site found whose behavioral
> effect on the proposed change must be verified by human review or tests.
>
> **Unknown** = areas static search cannot reach.

**Starting artifact:** `BILL-RATE`  | Type: `field`  | Language scope: `cobol`

---

## Confirmed Source References  (5 found)

### BILREC.BILL-RATE  `[DEFINES]`
- **Note:** Field defined in fictional representative COBOL copybook for BILREC.
- **Evidence:**
  - `src/QCBLSRC/BILREC.CPY:15` → `05  BILL-RATE     PIC 9(3)V99.`

### BILPRINT  `[READS_FIELD]`
- **Note:** Field referenced in src/QCBLSRC/BILPRINT.CBL. Verify usage is compatible with new value.
- **Evidence:**
  - `src/QCBLSRC/BILPRINT.CBL:29` → `MOVE BILL-RATE   TO WS-OUT-RATE`

### BILPRINT  `[COPY_MEMBER]`
- **Note:** BILPRINT COPYs {'BILREC'} — field is in scope.
- **Evidence:**
  - `src/QCBLSRC/BILPRINT.CBL:1` → `COPY`

### CALCBILL  `[READS_FIELD]`
- **Note:** Field referenced in src/QCBLSRC/CALCBILL.CBL. Verify usage is compatible with new value.
- **Evidence:**
  - `src/QCBLSRC/CALCBILL.CBL:26` → `COMPUTE BILL-AMOUNT = BILL-UNITS * BILL-RATE`

### CALCBILL  `[COPY_MEMBER]`
- **Note:** CALCBILL COPYs {'BILREC'} — field is in scope.
- **Evidence:**
  - `src/QCBLSRC/CALCBILL.CBL:1` → `COPY`

## Needs Review — Behavioral Impact Not Yet Determined  (0 items)

*(none)*

## Unknown / Out-of-Scope Areas

- Dynamic calls (variable program name) cannot be resolved by static search.
- COBOL ALTER / GO TO and computed CALL cannot be resolved.
- IBM i copy members (/COPY, /INCLUDE) and binding directory entries are not indexed.
- RPG fields accessed via locally-renamed variables may be missed.
- Predicate behavioral meaning (safe vs broken) is listed under 'needs-review' — confirm with business rules and executable tests.

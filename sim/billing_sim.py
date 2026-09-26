"""
billing_sim.py — Python Behavioral Simulation Harness (COBOL)
=============================================================
Legacy Retail Co — Change Impact Workbench demonstration

THIS IS A PYTHON SIMULATION, NOT COBOL EXECUTION.
It models the arithmetic logic from the representative COBOL source
files under src/QCBLSRC/.  No COBOL compiler or runtime is involved.

Change Request CR-3: Widen BILL-RATE from PIC 9(3)V99 to PIC 9(5)V99.
This copybook change affects CALCBILL (computes BILL-AMOUNT) and
BILPRINT (formats output picture) — both COPY BILREC.

Pre-change:  BILL-RATE max value 999.99  (PIC 9(3)V99)
Post-change: BILL-RATE max value 99999.99 (PIC 9(5)V99)

Boundary test: rate = 1000.00 (exceeds pre-change capacity)
  Pre-change:  overflow / truncation → incorrect amount
  Post-change: computed correctly
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List


# ---------------------------------------------------------------------------
# Data model — mirrors BILREC.CPY BILLING-RECORD
# ---------------------------------------------------------------------------

@dataclass
class BillingRecord:
    bill_acct:   str
    bill_name:   str
    bill_units:  int
    bill_rate:   Decimal   # PIC 9(3)V99 pre-change / PIC 9(5)V99 post-change
    bill_amount: Decimal   # computed
    bill_status: str       # 'O' | 'P' | 'D'


# ---------------------------------------------------------------------------
# Seed data factory
# ---------------------------------------------------------------------------

def make_billing_records() -> List[BillingRecord]:
    """Representative billing records for CR-3 demonstration."""
    return [
        BillingRecord("ACCT-001", "Customer Alpha",   100, Decimal("10.50"),  Decimal("0"), "O"),
        BillingRecord("ACCT-002", "Customer Beta",     50, Decimal("25.00"),  Decimal("0"), "O"),
        BillingRecord("ACCT-003", "Customer Gamma",   200, Decimal("999.99"), Decimal("0"), "O"),  # near pre-change limit
        BillingRecord("ACCT-004", "Customer Delta",     1, Decimal("1000.00"),Decimal("0"), "O"),  # exceeds pre-change 9(3)V99
    ]


# ---------------------------------------------------------------------------
# CALCBILL simulation — COMPUTE BILL-AMOUNT = BILL-UNITS * BILL-RATE
# Source: src/QCBLSRC/CALCBILL.CBL line 22
# ---------------------------------------------------------------------------

MAX_RATE_PRE  = Decimal("999.99")   # PIC 9(3)V99 upper bound
MAX_RATE_POST = Decimal("99999.99") # PIC 9(5)V99 upper bound


def calcbill_compute_pre_change(record: BillingRecord) -> Decimal:
    """
    Pre-change: BILL-RATE limited to PIC 9(3)V99.
    Rates exceeding 999.99 are truncated to 999.99 (overflow simulation).
    Source: CALCBILL.CBL L22  +  BILREC.CPY BILL-RATE PIC 9(3)V99
    """
    effective_rate = min(record.bill_rate, MAX_RATE_PRE)
    return (record.bill_units * effective_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcbill_compute_post_change(record: BillingRecord) -> Decimal:
    """
    Post-change (CR-3): BILL-RATE widened to PIC 9(5)V99.
    Rates up to 99999.99 computed correctly.
    Source: CALCBILL.CBL L22  +  BILREC.CPY BILL-RATE PIC 9(5)V99 (proposed)
    """
    effective_rate = min(record.bill_rate, MAX_RATE_POST)
    return (record.bill_units * effective_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_all(records: List[BillingRecord], post_change: bool = False) -> List[BillingRecord]:
    """Run CALCBILL logic over all records; returns new records with bill_amount populated."""
    fn = calcbill_compute_post_change if post_change else calcbill_compute_pre_change
    result = []
    for r in records:
        result.append(BillingRecord(
            r.bill_acct, r.bill_name, r.bill_units, r.bill_rate,
            fn(r), r.bill_status,
        ))
    return result

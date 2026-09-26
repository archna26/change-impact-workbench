"""
retailco_sim.py — Python Behavioral Simulation Harness
=======================================================
Legacy Retail Co — Change Impact Workbench demonstration

THIS IS A PYTHON SIMULATION, NOT IBM i EXECUTION.
It models the SQL predicate and business-rule logic written in the
representative RPG ILE source files under src/QRPGLESRC/.  No IBM i
compiler, runtime, or DB2 for i instance is involved.

Each function below maps to one sub-function in the corresponding
RPG program and implements the identical predicate logic in Python.
The predicate text is quoted verbatim from the source file.

Seed data
---------
Five orders placed today:
  1001  O  Open      REP1  ITEM-A  qty 5  @ $10.00  = $ 50.00
  1002  P  Picking   REP1  ITEM-B  qty 2  @ $25.00  = $ 50.00
  1003  C  Closed    REP2  ITEM-C  qty 1  @ $100.00 = $100.00
  1004  X  Cancelled REP2  ITEM-A  qty 3  @ $10.00  = $ 30.00
  1005  H  Hold(new) REP1  ITEM-B  qty 4  @ $25.00  = $100.00

Commission rate: 5% flat on order amount (simplified from COMMBRAK).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import List, Dict
import datetime

TODAY = datetime.date.today()
COMM_RATE = Decimal("0.05")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class OrderLine:
    itemno: str
    qty: int
    price: Decimal   # unit price (already resolved by PRICECALC equivalent)

    @property
    def extamt(self) -> Decimal:
        return (self.qty * self.price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Order:
    ordno: int
    custno: str
    salesrep: str
    ordsts: str          # 'O' | 'P' | 'C' | 'X' | 'H'
    ord_date: datetime.date
    lines: List[OrderLine] = field(default_factory=list)

    @property
    def order_amt(self) -> Decimal:
        return sum(l.extamt for l in self.lines)


@dataclass
class CommissionRecord:
    ordno: int
    salesrep: str
    order_amt: Decimal
    commission: Decimal


# ---------------------------------------------------------------------------
# Seed data factory
# ---------------------------------------------------------------------------

def make_baseline_orders() -> List[Order]:
    """Four orders — no 'H' status (pre-change baseline)."""
    return [
        Order(1001, "C01", "REP1", "O", TODAY, [OrderLine("ITEM-A", 5, Decimal("10.00"))]),
        Order(1002, "C02", "REP1", "P", TODAY, [OrderLine("ITEM-B", 2, Decimal("25.00"))]),
        Order(1003, "C03", "REP2", "C", TODAY, [OrderLine("ITEM-C", 1, Decimal("100.00"))]),
        Order(1004, "C04", "REP2", "X", TODAY, [OrderLine("ITEM-A", 3, Decimal("10.00"))]),
    ]


def make_incomplete_change_orders() -> List[Order]:
    """Five orders — includes order 1005 with new 'H' status.
    ORDENTRY updated to allow H; batch programs NOT yet updated."""
    orders = make_baseline_orders()
    orders.append(
        Order(1005, "C05", "REP1", "H", TODAY, [OrderLine("ITEM-B", 4, Decimal("25.00"))])
    )
    return orders


def make_fixed_orders() -> List[Order]:
    """Same five orders — batch programs now correctly handle 'H'."""
    return make_incomplete_change_orders()   # same data; fix is in the predicates below


# ---------------------------------------------------------------------------
# INVUPDJOB — sub-function ALLOC_ORDERS
# Source: src/QRPGLESRC/INVUPDJOB.RPGLE lines 25-31
# Predicate: WHERE h.ORDSTS = 'O'
# Status after CR-1: SAFE — positive predicate, H not included.
# ---------------------------------------------------------------------------

def invupdjob_alloc_orders(orders: List[Order]) -> List[int]:
    """
    Returns list of ORDNOs allocated to Picking.
    Simulates: WHERE h.ORDSTS = 'O'
    """
    return [o.ordno for o in orders if o.ordsts == "O"]


# ---------------------------------------------------------------------------
# INVUPDJOB — sub-function GEN_PICKLIST (pre-fix / broken)
# Source: src/QRPGLESRC/INVUPDJOB.RPGLE lines 51-58
# Predicate: WHERE h.ORDSTS <> 'C' AND h.ORDSTS <> 'X'
# Pre-change: {not C, not X} = {O, P} — correct.
# After CR-1 incomplete change: H satisfies this — BUG.
# ---------------------------------------------------------------------------

def invupdjob_gen_picklist_broken(orders: List[Order]) -> List[int]:
    """
    BROKEN predicate (pre-fix).
    Simulates: WHERE h.ORDSTS <> 'C' AND h.ORDSTS <> 'X'
    After adding H: held orders land on pick list — INV-1 violated.
    """
    return [o.ordno for o in orders if o.ordsts != "C" and o.ordsts != "X"]


def invupdjob_gen_picklist_fixed(orders: List[Order]) -> List[int]:
    """
    FIXED predicate (positive, explicit).
    Simulates: WHERE h.ORDSTS IN ('O', 'P')
    H is excluded — INV-1 preserved.
    """
    return [o.ordno for o in orders if o.ordsts in ("O", "P")]


# ---------------------------------------------------------------------------
# COMMJOB — sub-function CalcDailyComm (pre-fix / broken)
# Source: src/QRPGLESRC/COMMJOB.RPGLE lines 29-37
# Predicate: WHERE h.ORDSTS NOT IN ('O', 'C', 'X') AND h.ORD_DATE = CURRENT_DATE
# Pre-change: NOT IN ('O','C','X') resolves to {P} — correct.
# After CR-1 incomplete change: H satisfies NOT IN — BUG.
# ---------------------------------------------------------------------------

def commjob_calc_commission_broken(orders: List[Order]) -> List[CommissionRecord]:
    """
    BROKEN predicate (pre-fix).
    Simulates: WHERE h.ORDSTS NOT IN ('O', 'C', 'X') AND h.ORD_DATE = CURRENT_DATE
    After adding H: commission paid on held orders — INV-2 violated.
    """
    records = []
    for o in orders:
        if o.ordsts not in ("O", "C", "X") and o.ord_date == TODAY:
            comm = (o.order_amt * COMM_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            records.append(CommissionRecord(o.ordno, o.salesrep, o.order_amt, comm))
    return records


def commjob_calc_commission_fixed(orders: List[Order]) -> List[CommissionRecord]:
    """
    FIXED predicate (explicit positive).
    Simulates: WHERE h.ORDSTS = 'P' AND h.ORD_DATE = CURRENT_DATE
    H is excluded — INV-2 preserved.
    """
    records = []
    for o in orders:
        if o.ordsts == "P" and o.ord_date == TODAY:
            comm = (o.order_amt * COMM_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            records.append(CommissionRecord(o.ordno, o.salesrep, o.order_amt, comm))
    return records


# ---------------------------------------------------------------------------
# PRICECALC — CalcPrice (CR-2 rounding change demo)
# Source: src/QRPGLESRC/PRICECALC.RPGLE lines 35-42
# Pre-change:  HALF_UP rounding
# Post-change: HALF_EVEN (banker's rounding)
# Boundary case: $1.225 × 1 → HALF_UP=$1.23, HALF_EVEN=$1.22
# ---------------------------------------------------------------------------

def pricecalc_half_up(base_price: Decimal, qty: int) -> Decimal:
    """Pre-change: HALF_UP rounding (standard retail)."""
    if qty >= 10:
        raw = base_price * Decimal("0.95")
    else:
        raw = base_price
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pricecalc_half_even(base_price: Decimal, qty: int) -> Decimal:
    """Post-change (CR-2): HALF_EVEN / banker's rounding."""
    if qty >= 10:
        raw = base_price * Decimal("0.95")
    else:
        raw = base_price
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


# ---------------------------------------------------------------------------
# Convenience summary helpers
# ---------------------------------------------------------------------------

def commission_by_rep(records: List[CommissionRecord]) -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    for r in records:
        totals[r.salesrep] = totals.get(r.salesrep, Decimal("0.00")) + r.commission
    return totals

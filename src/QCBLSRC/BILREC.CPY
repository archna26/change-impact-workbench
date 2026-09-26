      *----------------------------------------------------------------
      * BILREC.CPY — Billing Record Copybook
      * Legacy Retail Co — fictional representative COBOL source
      * Modelled on real COBOL conventions but NOT compiled or run.
      *
      * This copybook defines the shared billing record structure
      * used by CALCBILL (calculation) and BILPRINT (print/output).
      * CR-3: changing BILL-RATE from PIC 9(3)V99 to PIC 9(5)V99
      *   affects every program that COPYs this member.
      *----------------------------------------------------------------
       01  BILLING-RECORD.
           05  BILL-ACCT     PIC X(10).
           05  BILL-NAME     PIC X(30).
           05  BILL-UNITS    PIC 9(7).
           05  BILL-RATE     PIC 9(3)V99.
           05  BILL-AMOUNT   PIC 9(9)V99.
           05  BILL-STATUS   PIC X(1).
               88  BILL-OPEN     VALUE 'O'.
               88  BILL-PAID     VALUE 'P'.
               88  BILL-DISPUTE  VALUE 'D'.

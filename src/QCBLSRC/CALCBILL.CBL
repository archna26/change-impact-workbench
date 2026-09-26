       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALCBILL.
      *----------------------------------------------------------------
      * CALCBILL.CBL — Billing Calculation Program
      * Legacy Retail Co — fictional representative COBOL source
      * Modelled on real COBOL conventions but NOT compiled or run.
      * Behavior is simulated in sim/billing_sim.py.
      *
      * Computes BILL-AMOUNT = BILL-UNITS * BILL-RATE for each
      * billing record and calls BILPRINT to produce the output.
      * CR-3: widening BILL-RATE in BILREC.CPY changes the arithmetic
      *   precision here — all computed amounts affected.
      *----------------------------------------------------------------
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY BILREC.

       PROCEDURE DIVISION.

       MAIN-PARA.
      *    Read billing input file (omitted for brevity)

      *    L22: Compute bill amount
           COMPUTE BILL-AMOUNT = BILL-UNITS * BILL-RATE

      *    L25: Call output/print program
           CALL 'BILPRINT' USING BILLING-RECORD

           STOP RUN.

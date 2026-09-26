       IDENTIFICATION DIVISION.
       PROGRAM-ID. BILPRINT.
      *----------------------------------------------------------------
      * BILPRINT.CBL — Billing Print / Output Program
      * Legacy Retail Co — fictional representative COBOL source
      * Modelled on real COBOL conventions but NOT compiled or run.
      * Behavior is simulated in sim/billing_sim.py.
      *
      * Called by CALCBILL. Formats and writes billing records to
      * the output spool/file. COPYs BILREC to access the shared
      * record layout.
      * CR-3: widening BILL-RATE in BILREC.CPY also affects the
      *   output format picture clause here (L28).
      *----------------------------------------------------------------
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY BILREC.

       PROCEDURE DIVISION.

       PRINT-PARA.
      *    L23: Format output line using BILL-AMOUNT
           MOVE BILL-ACCT   TO WS-OUT-ACCT
           MOVE BILL-AMOUNT TO WS-OUT-AMOUNT

      *    L28: Display rate (picture width tied to BILL-RATE definition)
           MOVE BILL-RATE   TO WS-OUT-RATE

      *    Write to spool (omitted for brevity)
           STOP RUN.

      *----------------------------------------------------------------
      * INVUPDJOB - Batch Inventory Update and Pick-List Generation
      * RETAILCO fictional IBM i application
      * Representative RPG ILE free-format syntax — not compiled or
      * run on IBM i. Behavior is simulated in sim/retailco_sim.py.
      *
      * Two sub-functions:
      *   ALLOC_ORDERS  - allocates QOH to Open orders (safe after CR-1)
      *   GEN_PICKLIST  - generates warehouse pick-list extract (broken)
      *----------------------------------------------------------------
      **FREE

       Dcl-F ORDHDR  Usage(*Input:*Update) Keyed;
       Dcl-F ORDLIN  Usage(*Input);
       Dcl-F ITEMMST Usage(*Update) Keyed;

       // ---- Sub-function: ALLOC_ORDERS ----------------------------
       // Selects only ORDSTS = 'O' (exact match).
       // CR-1 impact: H orders do NOT satisfy = 'O'.
       // Result: allocation sub-function is SAFE after adding H.
       //
       Dcl-Proc AllocOrders;

         // L44: SQL — allocate Open orders only
         Exec SQL
           DECLARE c_alloc CURSOR FOR
             SELECT h.ORDNO, l.ITEMNO, l.QTY
               FROM ORDHDR h
               JOIN ORDLIN l ON h.ORDNO = l.ORDNO
              WHERE h.ORDSTS = 'O'           -- only Open orders
              ORDER BY h.ORDNO;

         // For each row: update ITEMMST.ALLOC, set ORDSTS = 'P'
         // ... (fetch loop omitted for brevity)

       End-Proc;

       // ---- Sub-function: GEN_PICKLIST ----------------------------
       // Uses a NEGATIVE predicate: not-closed AND not-cancelled.
       // Pre-change assumption: {not C, not X} = {O, P} = all actionable.
       // CR-1 BREAKS THIS: H satisfies <> 'C' AND <> 'X',
       //   so held orders land on the warehouse pick list.
       // Business invariant INV-1 violated: held orders must NOT
       //   reach the warehouse floor.
       //
       Dcl-Proc GenPickList;

         // L67: SQL — pick list for all "actionable" orders
         //       Pre-change: <>'C' AND <>'X' correctly captured {O,P}
         //       Post-change (incomplete): now also captures {H} — BUG
         Exec SQL
           DECLARE c_pick CURSOR FOR
             SELECT h.ORDNO, h.CUSTNO, l.ITEMNO, l.QTY, l.PRICE
               FROM ORDHDR h
               JOIN ORDLIN l ON h.ORDNO = l.ORDNO
              WHERE h.ORDSTS <> 'C'          -- not closed
                AND h.ORDSTS <> 'X'          -- not cancelled
              ORDER BY h.ORDNO, l.LINESEQ;

         // Write pick list spool / extract
         // ... (fetch/write loop omitted for brevity)

       End-Proc;

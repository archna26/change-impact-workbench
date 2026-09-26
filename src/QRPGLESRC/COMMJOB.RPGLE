      *----------------------------------------------------------------
      * COMMJOB - Daily Sales Commission Calculation
      * RETAILCO fictional IBM i application
      * Representative RPG ILE free-format syntax — not compiled or
      * run on IBM i. Behavior is simulated in sim/retailco_sim.py.
      *
      * Calculates commission for orders that progressed past Open
      * today. Pre-change: ORDSTS NOT IN ('O','C','X') == {P} only.
      * CR-1 BREAKS THIS: H also satisfies NOT IN ('O','C','X').
      * Result: commission paid on held orders — INV-2 violated.
      *----------------------------------------------------------------
      **FREE

       Dcl-F ORDHDR   Usage(*Input);
       Dcl-F ORDLIN   Usage(*Input);
       Dcl-F COMMBRAK Usage(*Input) Keyed;

       Dcl-S wSalesRep  Char(6);
       Dcl-S wOrdAmt    Packed(11:2);
       Dcl-S wCommRate  Packed(5:4);
       Dcl-S wCommAmt   Packed(11:2);

       Dcl-Proc CalcDailyComm;

         // L31: SQL — select "in-progress" orders for today
         //   Pre-change: NOT IN ('O','C','X') resolves to {P} only
         //   Post-change (incomplete): H satisfies NOT IN — BUG
         //   Fix: change to ORDSTS = 'P' (explicit positive predicate)
         Exec SQL
           DECLARE c_comm CURSOR FOR
             SELECT h.ORDNO, h.SALESREP,
                    SUM(l.QTY * l.PRICE) AS ORDER_AMT
               FROM ORDHDR h
               JOIN ORDLIN l ON h.ORDNO = l.ORDNO
              WHERE h.ORDSTS NOT IN ('O', 'C', 'X')  -- "in progress" today
                AND h.ORD_DATE = CURRENT_DATE
              GROUP BY h.ORDNO, h.SALESREP;

         // For each order: look up bracket rate, write commission record
         // ... (fetch/lookup loop omitted for brevity)

       End-Proc;

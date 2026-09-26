      *----------------------------------------------------------------
      * INVPRICJOB - Batch Invoice Price Recalculation Job
      * RETAILCO fictional IBM i application
      * Representative RPG ILE free-format syntax — not compiled or
      * run on IBM i. Behavior is simulated in sim/retailco_sim.py.
      *
      * Runs nightly to recompute line prices on any open order that
      * was created without a confirmed price (e.g. during a system
      * outage) and to reprice EDI imports before invoice generation.
      * Directly calls PRICECALC — CR-2 rounding change affects every
      * line price this job writes to ORDLIN.PRICE.
      *----------------------------------------------------------------
      **FREE

       Dcl-F ORDHDR  Usage(*Input);
       Dcl-F ORDLIN  Usage(*Update) Keyed;
       Dcl-F ITEMMST Usage(*Input)  Keyed;

       // ---- Prototype for PRICECALC service program ----------------
       Dcl-PR CalcPrice  ExtPgm('PRICECALC');
         pItemNo    Char(8)   Const;
         pQty       Packed(7:0) Const;
         pBasePrice Packed(11:2) Const;
         pFinalPrice Packed(11:2);
       End-PR;

       Dcl-S wFinal    Packed(11:2);

       Dcl-Proc RepriceBatch;

         // L31: Select open orders that need price confirmation
         Exec SQL
           DECLARE c_reprice CURSOR FOR
             SELECT h.ORDNO, l.LINESEQ, l.ITEMNO, l.QTY,
                    i.SELL_PRICE AS BASE_PRICE
               FROM ORDHDR h
               JOIN ORDLIN  l ON h.ORDNO  = l.ORDNO
               JOIN ITEMMST i ON l.ITEMNO = i.ITEMNO
              WHERE h.ORDSTS IN ('O', 'P')   -- open orders only
              ORDER BY h.ORDNO, l.LINESEQ;

         // For each line: call PRICECALC, update ORDLIN.PRICE
         // L41: Call PRICECALC — rounding change (CR-2) flows here
         CalcPrice(wItemNo : wQty : wBasePrice : wFinal);

         // Update ORDLIN with confirmed price
         PRICE  = wFinal;
         EXTAMT = wQty * wFinal;
         Update ORDLINR;

       End-Proc;

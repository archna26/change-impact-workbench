      *----------------------------------------------------------------
      * ORDENTRY - Interactive Order Entry
      * RETAILCO fictional IBM i application
      * Representative RPG ILE free-format syntax — not compiled or
      * run on IBM i. Behavior is simulated in sim/retailco_sim.py.
      *----------------------------------------------------------------
      **FREE

       // ---- File declarations (externally described) ---------------
       Dcl-F ORDHDR  Usage(*Update:*Output) Keyed;
       Dcl-F ORDLIN  Usage(*Output);

       // ---- Prototype for PRICECALC service program ----------------
       Dcl-PR CalcPrice  ExtPgm('PRICECALC');
         pItemNo    Char(8)   Const;
         pQty       Packed(7:0) Const;
         pBasePrice Packed(11:2) Const;
         pFinalPrice Packed(11:2);
       End-PR;

       // ---- Standalone fields ---------------------------------------
       Dcl-S wOrdNo    Packed(7:0);
       Dcl-S wOrdSts   Char(1);
       Dcl-S wItemNo   Char(8);
       Dcl-S wQty      Packed(7:0);
       Dcl-S wPrice    Packed(11:2);
       Dcl-S wFinal    Packed(11:2);

       // ---- Main entry point ----------------------------------------
       Dcl-Proc OrderEntry;

         // Read screen input (display file omitted for brevity)
         // wOrdNo, wOrdSts, wItemNo, wQty, wPrice populated from screen

         // ----------------------------------------------------------
         // L18: Validate order status
         // Pre-change valid set: O, P, C, X
         // Post-change (CR-1): add H to valid set
         // ----------------------------------------------------------
         If wOrdSts <> 'O' And
            wOrdSts <> 'P' And
            wOrdSts <> 'C' And
            wOrdSts <> 'X';
           // Signal invalid status error
           Return;
         EndIf;

         // ----------------------------------------------------------
         // L55: Call PRICECALC to resolve unit price
         // PRICECALC is a shared service program called by all order
         // entry paths. Any change to rounding logic inside PRICECALC
         // affects this caller's computed line amounts.
         // ----------------------------------------------------------
         CalcPrice(wItemNo : wQty : wPrice : wFinal);

         // Write order header
         ORDNO    = wOrdNo;
         ORDSTS   = wOrdSts;
         ORD_DATE = %Date();
         Write ORDHDRR;

         // Write order line
         ITEMNO = wItemNo;
         QTY    = wQty;
         PRICE  = wFinal;
         EXTAMT = wQty * wFinal;
         Write ORDLINR;

       End-Proc;

      *----------------------------------------------------------------
      * PRICECALC - Price Calculation Service Program
      * RETAILCO fictional IBM i application
      * Representative RPG ILE free-format syntax — not compiled or
      * run on IBM i. Behavior is simulated in sim/retailco_sim.py.
      *
      * Shared service program called by all order-entry paths.
      * CR-2: changing the rounding mode (HALF_UP -> HALF_EVEN) here
      * affects every caller: ORDENTRY and ORDENTRY2.
      * INVUPDJOB and COMMJOB do NOT call PRICECALC — correctly excluded.
      *----------------------------------------------------------------
      **FREE

       // ---- Export procedure: CalcPrice ----------------------------
       // Parameters:
       //   pItemNo    - item number (input)
       //   pQty       - quantity ordered (input)
       //   pBasePrice - catalogue base price (input)
       //   pFinalPrice - resolved unit price (output)
       //
       // Rounding rule (pre-change): HALF_UP (standard retail)
       // Rounding rule (post-change CR-2): HALF_EVEN (banker's rounding)
       //   Boundary case: $1.225 * 1 => HALF_UP=$1.23, HALF_EVEN=$1.22
       //
       Dcl-Proc CalcPrice Export;
         Dcl-PI *N;
           pItemNo     Char(8)     Const;
           pQty        Packed(7:0) Const;
           pBasePrice  Packed(11:2) Const;
           pFinalPrice Packed(11:2);
         End-PI;

         Dcl-S wRounded Packed(11:2);

         // L35: Apply volume discount (5% for qty >= 10)
         If pQty >= 10;
           wRounded = pBasePrice * 0.95;
         Else;
           wRounded = pBasePrice;
         EndIf;

         // L42: Round to 2 decimal places
         // Pre-change: HALF_UP rounding
         // Post-change (CR-2): HALF_EVEN — changes output for .5 cases
         pFinalPrice = %Dec(wRounded : 11 : 2);   // RPG default: HALF_UP

       End-Proc;

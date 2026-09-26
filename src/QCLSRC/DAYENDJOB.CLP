 /*----------------------------------------------------------------*/
 /* DAYENDJOB - End-of-Day Batch Driver                            */
 /* RETAILCO fictional IBM i application                           */
 /* Representative CL syntax — not compiled or run on IBM i       */
 /*----------------------------------------------------------------*/
 PGM

   /* Step 1: Run inventory allocation and pick-list generation    */
   /* INVUPDJOB contains both ALLOC_ORDERS and GEN_PICKLIST        */
   CALL PGM(INVUPDJOB)

   /* Step 2: Calculate daily sales commissions                    */
   CALL PGM(COMMJOB)

 ENDPGM

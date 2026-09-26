 /*----------------------------------------------------------------*/
 /* STMTJOB - Monthly Customer Statement Print Job                */
 /* RETAILCO fictional IBM i application                          */
 /* Representative CL syntax — not compiled or run on IBM i      */
 /*                                                               */
 /* Reads already-committed order and invoice data to produce     */
 /* customer statements. Does NOT reprice lines — prices are      */
 /* already confirmed by INVPRICJOB before this job runs.         */
 /* CR-2 (PRICECALC rounding change) does NOT affect this job.   */
 /*----------------------------------------------------------------*/
 PGM

   /* Step 1: Run batch price recalculation before printing       */
   CALL PGM(INVPRICJOB)

   /* Step 2: Generate and spool customer statements              */
   /* (statement formatting program not shown)                    */

 ENDPGM

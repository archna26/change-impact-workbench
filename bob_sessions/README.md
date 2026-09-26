# bob_sessions — Task Session Consumption Screenshots

This folder holds the Bob task session consumption summary screenshots
required for the IBM Bob 2.0 Hackathon submission.

## How to capture

For each Bob task session in this project:

1. In the Bob IDE, look at the **task header breadcrumb** at the top of the chat pane.
2. Click the task header — a "Task session consumption summary" popup appears
   (as shown in Figures 21–23 of the submission guide).
3. Take a screenshot of that popup.
4. Save as PNG with this naming pattern:

   ```
   teamname_task<NN>_<short-description>.png
   ```

## Screenshot inventory for this project

The Change Impact Workbench was built across these task sessions.
Capture one screenshot per task:

| File name to create | Task description |
|---------------------|-----------------|
| `archana_task01_baseline-plan.png` | Initial plan: workspace inspection, fictional IBM i system proposal, Candidate C selection |
| `archana_task02_candidate-revision.png` | Candidate C predicate logic correction (pick-list + commission failures) |
| `archana_task03_product-scope.png` | Scope change: reusable Change Impact Workbench, two change requests, COBOL extension |
| `archana_task04_ibmi-skeleton.png` | IBM i source skeleton (DDS, RPG, CL), answer key, ciw_engine P0 |
| `archana_task05_engine-indexer.png` | ciw_engine.py indexer + traverser + report builder, first ORDSTS run |
| `archana_task06_semantics-fix.png` | Report semantics fix: WRITES_FIELD, needs-review, INDIRECT_CALLER |
| `archana_task07_cobol-extension.png` | COBOL adapter, BILREC/CALCBILL/BILPRINT, billing_sim.py, test_cobol_billing.py |
| `archana_task08_release-readiness.png` | Release-readiness: demo marker isolation, catalog counts, naming, green suite |

## Submission checklist

- [ ] All PNG files saved to this folder
- [ ] File names follow the `teamname_taskNN_description.png` pattern
- [ ] Each screenshot shows the consumption summary popup (tokens used, turns, duration)
- [ ] Folder committed and pushed before submission deadline: 27 Sep 2026 20:30 IST

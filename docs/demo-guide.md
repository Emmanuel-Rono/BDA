# Five-minute BDA walkthrough

1. Open port 8002 and enter this project's own private access token.
2. Show **LIVE SPREE**, then show draft order **R1001** in Spree with quantity three.
3. Use the demo pair or upload `examples/live-invoice.pdf` and
   `examples/live-packing-slip.pdf`. The invoice lists three; the slip lists two.
4. Wait for actual local inference. Show each extracted field's page quote.
5. Show Python's quantity comparison: three ordered, three invoiced, two packed.
6. Explain why minus one needs review and may be a partial shipment.
7. Add a review note and approve/reject the internal report. Spree stays unchanged.
8. Repeat the same upload and show the existing job instead of another model run.

Explain the code path: `documents.py` parses → `extraction.py` asks Qwen and checks
quotes → `spree.py` reads the matching order → `reconcile.py` calculates →
`storage.py` saves the job and review.

CV wording after verification: “Built a local commerce document prototype that
extracts source-backed invoice fields, compares quantities with Spree orders,
and saves discrepancy reports for human review.”

Call this first version a fixed AI-assisted workflow. It does not autonomously
plan actions, run OCR, translate languages or change stock. Publish BDA as a
separate source repository and include a short demo recording.

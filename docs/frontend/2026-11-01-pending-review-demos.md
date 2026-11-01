# Three pending human-review demonstrations

At the user's request, added three fictional reports to the live Pending queue:

- Duplicate rent demand after a recorded payment.
- Kitchen leak awaiting a repair appointment.
- Electricity charges after the keys were returned.

Each report has a different category, descriptive `[Demo]` title, original
fictional description, illustrative evidence excerpts and a requested review
outcome. No actual documents, bank accounts, property contacts or external AI
calls are involved. Each has a separate current-format empty case so the existing
View report and review-advice workflow remain valid.

These are normal editable pending reports rather than the read-only historical
example cards. Saving advice moves them to History through the existing version
and request-receipt checks. No advice has been submitted on the user's behalf.
The original five historical examples are unchanged.

Seeding used stable request IDs and an incremental local manifest to avoid
creating duplicates on retry. Pre-seed database backups and the manifest are in
`.runtime-backups/pending-review-seed-20261101/` (ignored by Git). The descriptive
titles were aligned in the newly authored fixture records and creation receipts;
original report descriptions, versions and consent behavior were unchanged.

Live API/browser verification: Pending 3, History 5; distinct demo titles; advice
entry and completion buttons enabled. A browser refresh or Refresh reports loads
the new records. Restarting services does not automatically reseed or reopen them.

Adding multiple pending cards exposed duplicate Ant Design form IDs: each advice
label targeted `note`, so only the first textarea had the correct accessible
label. Give every card a form name bound to kind, case and report IDs. An isolated
browser regression first reproduced the failure, then verifies three independent
advice fields and saving only the selected report's advice. Live demonstration
reports remain pending; verification does not complete them on the user's behalf.

# Simple local human review and evidence

User explicitly requests removing the reviewer-key function. Open the local review queue directly, including without an active tenant case. Preserve version checks, explicit decision saves, original reports and case-scoped files. Keep existing tenant data and consent/RAG/Jev flows unchanged.

- [x] Test key-free queue/decisions and report attachments, including cross-case rejection, retries, downloads and persistence.
- [x] Reuse JPEG/PNG/PDF local uploads (10 MiB each); bind up to ten attachment IDs per report/update with server ownership checks; expose only linked metadata in tenant and reviewer records.
- [x] Replace reviewer UI with an automatically loaded list and per-report details: issue/reason, reported content/requested help, evidence previews/downloads, and one advice field with explicit save/completion. Preserve contract review support and prior decisions.
- [x] Add evidence uploading to report/reply forms with stable upload request IDs, visible failed uploads, retry/removal and submission blocked until selected files finish.
- [x] Verify synthetic API/browser flows, mobile layout, meaningful failures, original history and no active-case queue access. Sync documentation/public guide; reload services preserving actual configuration and saved data.

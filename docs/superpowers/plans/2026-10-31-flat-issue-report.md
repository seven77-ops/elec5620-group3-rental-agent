# Flat issue reporting

User requests replacing the Move-out and bond surface with Issue report and exactly two inner tabs: Report issue and History. The inline form contains issue type, original description and optional evidence files; date is assigned by the server. No visible case, tenancy intake, plan, bond activation, reminders, title or requested-outcome inputs. Reports cover rent/bond, furniture, repairs, during tenancy, moving out, after moving out and other. Preserve all saved records and evidence and keep Human review advice connected.

- [x] Add direct report create/history/advice API on web storage, without fabricating confirmed tenancy. Reuse bounded local attachments and validate ownership. Keep receipts, versions, server dates, immutable descriptions and existing old Agent4 reviews.
- [x] Add flat IssueReport form/history using the existing upload/preview components; hide housing context panels on this tab, preserve other living tabs and old URL aliases.
- [x] Extend Human review to new reports and preserve old records; update progress counts and links to History.
- [x] Test no-tenancy submission, all types, attachment history/advice, old report compatibility, retry/version/cross-case boundaries and mobile layout. Update current guide/docs and load local changes while preserving runtime config and data.

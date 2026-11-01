# Aftercare home toolbar

Replace the three large context panels with My home and In progress buttons beside Load latest information. My home contains only address/suburb/postcode and agent/landlord name/email/phone, with concise source labels and explicit basic editing. Auto-display selected listing facts as reference, never fabricate occupancy or write on read; saved home/contact data wins, and draft contacts must match the shown address. Keep all existing hidden profile fields, repairs, bookings, files and explicit saves intact.

In progress collects unresolved repairs and non-completed service records, including past booked services not marked complete; exclude prompts to add contacts. Opening an item closes the drawer and focuses its existing record. Issue report keeps its flat form and history, with toolbar buttons available without restoring context panels.

- [x] Test read-only home handoff, saved-data precedence, same-home draft contacts, no invented/mixed sources and profile preservation.
- [x] Implement home summary API and basic drawer; reuse existing profile write/version/receipt contract with explicit Save details.
- [x] Implement in-progress collection/drawer and toolbar integration, removing always-visible panels.
- [x] Verify desktop/mobile, edit preservation, item navigation, issue-page simplicity; sync docs and load changes preserving actual service config and user data.

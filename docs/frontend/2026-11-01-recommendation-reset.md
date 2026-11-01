# Unrestricted housing filter reset

Area now includes an explicit **All areas** choice. Applying it removes the
suburb restriction while retaining the other form values. The option is also
searchable by its label.

**Reset filters** immediately clears the area, room/parking minimums, rent ceiling,
commute mode/time and hidden transfer restriction. It restores weekly rent
ascending, returns pagination to page one and reloads the unrestricted catalogue.
It clears stale edited-filter notices and adjustment suggestions. Empty numeric
fields mean unrestricted; setting the rent ceiling to zero would incorrectly
exclude listings.

Reset is a local catalogue filter action; saved rental needs and the selected
follow-up property remain intact. **Restore preference filters** still restores
the saved needs separately. A reset made while preference context is loading is
not overwritten when that request returns.

Validation covers All areas preserving other filters, reset sending only case ID,
page/page-size and default sort, complete catalogue count, cleared visible and
hidden fields, unchanged saved case data and delayed preference loading.


Verification: the two new reset scenarios and two recommendation-workbench
scenarios passed; all four USYD housing scenarios passed on rerun. One pre-existing
chat assertion expected the retired `~N min` label and was updated to the current
`Commute N min` presentation. No commute logic changed. All 73 frontend unit tests,
frontend build, targeted formatting and diff checks passed. The existing vendor
chunk-size warning remains.

A read-only live-browser check on the user's case confirmed All areas is present;
reset returns 1000 listings with only case ID, page/page-size and `sort=rent_asc`
in the request. All five numeric filter fields are empty and the page is 1.

"""Reviewed English public-source registry. No user-supplied crawl URLs."""
SOURCES=[
 ('repairs','Getting repairs done on a rental property','https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/getting-repairs-done'),
 ('bond-refund','Getting your bond back at the end of a tenancy','https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/getting-your-bond-back'),
 ('ending-notice','Giving notice to end a residential tenancy','https://www.nsw.gov.au/housing-and-construction/rules/giving-notice-to-end-a-residential-tenancy'),
 ('break-lease','Breaking a fixed-term residential tenancy early','https://www.nsw.gov.au/housing-and-construction/rules/breaking-a-fixed-term-residential-tenancy-early'),
 ('disputes','Resolving residential tenancy disputes','https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/resolving-residential-tenancy-disputes'),
 ('standard-lease','Standard residential tenancy agreement','https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/resources/standard-residential-tenancy-agreement'),
 ('tenant-information','Tenant information statement','https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/resources/tenant-information-statement'),
 ('condition-reports','Rental property condition reports','https://www.nsw.gov.au/housing-and-construction/rules/rental-property-condition-reports'),
 ('shared-housing','Sharing a residential rental property','https://www.nsw.gov.au/housing-and-construction/rules/sharing-a-residential-rental-property'),
 ('student-off-campus','Off campus accommodation — University of Sydney','https://www.sydney.edu.au/study/accommodation/off-campus.html'),
 ('rent-increases','Tenants and rent increases','https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/rent-increases'),
 ('wear-and-damage','Fair wear and tear versus damage in rental properties','https://www.nsw.gov.au/housing-and-construction/rules/fair-wear-and-tear-versus-damage-rental-properties'),
 ('landlord-access','Minimum notice periods for access to rental property','https://www.nsw.gov.au/housing-and-construction/rules/minimum-notice-periods-for-access-to-rental-property'),
]

SOURCE_TYPES = {identifier: 'official_guidance' for identifier, _, _ in SOURCES}
SOURCE_TYPES.update({'standard-lease': 'official_template', 'student-off-campus': 'student_guidance'})

# Fixed public originals verified against their official landing pages on 2026-10-30.
# Refresh requires the landing page to still link the exact approved PDF URL.
PDF_DOWNLOADS = {
 'standard-lease': 'https://www.nsw.gov.au/sites/default/files/noindex/2025-06/residential-tenancy-agreement-form.pdf',
 'tenant-information': 'https://www.nsw.gov.au/sites/default/files/noindex/2025-05/tenant-information-statement.pdf',
}

# Pin reviewed originals, including the blank lease, so a replaced/filled document
# cannot silently become public knowledge. A changed official PDF requires review.
PDF_SHA256 = {
 'standard-lease': '5addb961d6864a794f1f5e44a74e21e5216e762eeeac9e176ec088c004480c64',
 'tenant-information': 'a4e0eb3924f1813bab83a75c4e97ae62ec9098be11d41e8abce9f2ede1213dce',
}

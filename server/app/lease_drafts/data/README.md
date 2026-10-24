# Australian locality/postcode reference

`au-localities.json` is an offline reference for optional, manually editable notice-address suggestions. It contains only `[suburb, state, postcode]` tuples. It is independent of rental listings and provides no street-address information or verification. It includes PO boxes and other delivery localities; an exact suburb may have several valid postcodes. Users must select the applicable option or enter their own value. Coverage and accuracy are limited to the upstream snapshot; this is not an official, current Australia Post verification service.

Source: Matthew Proctor's Australian Postcodes community database, described by the author as free public domain on [his homepage](https://www.matthewproctor.com/) (the researched homepage lines 51–54). [Source information and accuracy notes](https://www.matthewproctor.com/australian_postcodes). Attribution is retained here.

Pinned GitHub commit: `eda59e4a987d46dbfb1d6bc644a383d322aa3d8d` in `matthewproctor/australianpostcodes`.

Exact upstream file: https://raw.githubusercontent.com/matthewproctor/australianpostcodes/eda59e4a987d46dbfb1d6bc644a383d322aa3d8d/australian_postcodes.csv

Raw CSV SHA-256: `0cd6f0f9f70dafd4cda8d78d86f70233a12774e138a76e1331f6b9c4f3394dfc`

Reduced JSON SHA-256: `9ab69574de59210e33501e5590f0bd396f28f4978fbcd1a0245ee96b588c3a6c`

Reduction counts: 18,559 source rows, 0 invalid rows discarded, 24 duplicate rows removed, 18,535 distinct tuples retained.

To reproduce using an already downloaded copy of that pinned CSV (no network is used):

```sh
python3 server/app/lease_drafts/data/reduce_postcodes.py /path/to/australian_postcodes.csv /tmp/au-localities.json
```

The reducer reads only `locality`, `state`, and `postcode`, strips surrounding whitespace, normalizes locality with Python `.title()` and State to uppercase, keeps postcodes as strings (including leading zeroes), discards empty localities, unknown States and non-four-digit postcodes, deduplicates triples, and sorts by case-folded suburb, State, postcode. Output uses compact UTF-8 JSON arrays and one final newline. It prints reproducible row counts and both SHA-256 hashes. The raw CSV is not included or read at runtime. The runtime loads the reduced file lazily and caches it once per process.

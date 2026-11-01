"""Offline reduction: python reduce_postcodes.py source.csv [output.json]. No network."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

STATES = frozenset(('NSW', 'VIC', 'QLD', 'ACT', 'SA', 'WA', 'TAS', 'NT'))


def reduce_csv(raw):
    rows = set()
    counts = {'source_rows': 0, 'invalid_rows': 0, 'duplicate_rows': 0}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline='')):
        counts['source_rows'] += 1
        suburb = (row.get('locality') or '').strip().title()
        state = (row.get('state') or '').strip().upper()
        postcode = (row.get('postcode') or '').strip()
        if not suburb or state not in STATES or not re.fullmatch(r'[0-9]{4}', postcode):
            counts['invalid_rows'] += 1
            continue
        item = (suburb, state, postcode)
        if item in rows:
            counts['duplicate_rows'] += 1
        rows.add(item)
    # Arrays keep the reference compact; IDs are derived from these three fields.
    ordered = sorted(rows, key=lambda r: (r[0].casefold(), r[1], r[2]))
    reduced = (json.dumps(ordered, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    return reduced, {**counts, 'reduced_rows': len(ordered),
                     'source_sha256': hashlib.sha256(raw).hexdigest(),
                     'reduced_sha256': hashlib.sha256(reduced).hexdigest()}


if __name__ == '__main__':
    output, report = reduce_csv(Path(sys.argv[1]).read_bytes())
    destination = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name('au-localities.json')
    destination.write_bytes(output)
    print(json.dumps(report, indent=2))

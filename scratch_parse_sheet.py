import csv
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('google_sheet_export.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows in sheet: {len(rows)}")
categories = {}
for r in rows:
    cat = r.get('Platform / Category', '').strip()
    categories.setdefault(cat, []).append(r)

for cat, items in categories.items():
    print(f"\n=== {cat} ({len(items)} items) ===")
    for it in items:
        id_ = it.get('ID', '')
        name = it.get('Community / Channel / Account Name', '')
        handle = it.get('Handle / Identifier', '')
        url = it.get('Direct URL', '')
        angle = it.get('Research Angle / What to Mine', '')
        print(f"  [{id_}] {name} ({handle}) -> {url}")
        print(f"       Angle: {angle[:80]}...")

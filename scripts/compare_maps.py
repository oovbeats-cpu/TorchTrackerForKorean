import json

# Load both files
with open('src/titrack/data/items_ko.json', encoding='utf-8') as f:
    items_ko = json.load(f)

with open('output/crawler3_maps_items_only.json', encoding='utf-8') as f:
    crawled = json.load(f)

# Compare
mismatches = []
for item_id in crawled:
    if item_id in items_ko:
        if items_ko[item_id]['name'] != crawled[item_id]['name']:
            mismatches.append({
                'id': item_id,
                'old': items_ko[item_id]['name'],
                'new': crawled[item_id]['name']
            })

print(f"Total crawled items: {len(crawled)}")
print(f"Existing in items_ko.json: {len([k for k in crawled if k in items_ko])}")
print(f"Name mismatches: {len(mismatches)}")

if mismatches:
    print("\nMismatches found:")
    for m in mismatches[:10]:
        print(f"  {m['id']}: '{m['old']}' -> '{m['new']}'")
else:
    print("\nAll names match perfectly!")

# Statistics by category
compass = [k for k, v in crawled.items() if v['type'] == '나침반']
probe = [k for k, v in crawled.items() if v['type'] == '탐침']
season = [k for k, v in crawled.items() if v['type'] == '시즌 나침반']

print(f"\nBy category:")
print(f"  나침반: {len(compass)}")
print(f"  탐침: {len(probe)}")
print(f"  시즌 나침반: {len(season)}")

# Sample items
print(f"\nSample Compass items:")
for item_id in compass[:3]:
    print(f"  {item_id}: {crawled[item_id]['name']}")

print(f"\nSample Probe items:")
for item_id in probe[:3]:
    print(f"  {item_id}: {crawled[item_id]['name']}")

print(f"\nSample Season items:")
for item_id in season:
    print(f"  {item_id}: {crawled[item_id]['name']}")

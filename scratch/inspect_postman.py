import json

with open(r"D:\Projects\CHB Portal\CHB_Portal.postman_collection.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Collection: {data['info']['name']}")
print(f"Total top-level folders: {len(data['item'])}")
print()

for i, folder in enumerate(data["item"]):
    name = folder.get("name", "?")
    items = folder.get("item", [])
    print(f"  {i+1:2d}. {name} ({len(items)} endpoints)")
    for j, item in enumerate(items):
        method = item.get("request", {}).get("method", "?")
        iname = item.get("name", "?")
        print(f"        [{method}] {iname}")

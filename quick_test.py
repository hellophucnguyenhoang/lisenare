item_ids = ""

item_ids = [int(x.strip()) for x in item_ids.split(",") if x.strip().isdigit()]

print(f"INTERACTED ITEMS: {item_ids}")
print(not item_ids)

from modules.module5_usda_database import USDADatabase

db = USDADatabase()

print("Testing ingredient matching:\n")
for ing in ['chicken', 'rice', 'beef', 'egg', 'salmon']:
    r = db.lookup_single(ing)
    print(f"{ing:12} → {r['matched_to']:40} {r['calories_per_100g']} kcal, {r['protein_g']}g protein")

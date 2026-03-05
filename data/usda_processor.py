"""
NutriSync - USDA FoodData Central Processor (Fixed)
=====================================================
BUG FIX: Foundation Foods uses nutrient_id=2047 for calories
         SR Legacy uses nutrient_id=1008 for calories
         Previous version only looked for 1008 → 249 items had zero calories

FIX: We now collect calories from BOTH IDs and merge them.
     Priority: 2047 (Atwater General) > 1008 (Energy) > 2048 (Atwater Specific)

USAGE:
    python usda_processor.py

OUTPUT:
    data/processed/usda_nutrition_processed.csv
"""

import os
import zipfile
import pandas as pd

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH    = os.path.join(BASE_DIR, "processed", "usda_nutrition_processed.csv")
FOUNDATION_ZIP = os.path.join(BASE_DIR, "raw", "Food_Foundation_Foods.zip")
SR_LEGACY_ZIP  = os.path.join(BASE_DIR, "raw", "Food_SR_Legacy.zip")


# ─── Nutrient ID mapping ─────────────────────────────────────────────────────
# ROOT CAUSE OF BUG:
#   Foundation Foods → stores calories under nutrient_id 2047
#   SR Legacy        → stores calories under nutrient_id 1008
#   We now extract BOTH and merge, preferring 2047 when available

# All three calorie IDs to extract
CALORIE_IDS = [1008, 2047, 2048]

# All other nutrients (same IDs in both datasets - confirmed by inspection)
OTHER_NUTRIENT_IDS = {
    "protein_g"    : 1003,
    "fat_g"        : 1004,
    "carbs_g"      : 1005,
    "fiber_g"      : 1079,
    "sugar_g"      : 2000,
    "sodium_mg"    : 1093,
    "iron_mg"      : 1089,
    "magnesium_mg" : 1090,
    "calcium_mg"   : 1087,
    "potassium_mg" : 1092,
    "vitamin_c_mg" : 1162,
    "vitamin_d_mcg": 1114,
    "omega3_g"     : 1404,
}

# Combined map for processing (calories handled separately)
ID_TO_COL = {v: k for k, v in OTHER_NUTRIENT_IDS.items()}
ALL_TARGET_IDS = set(CALORIE_IDS) | set(OTHER_NUTRIENT_IDS.values())


# ─── Categories to keep ──────────────────────────────────────────────────────
KEEP_CATEGORY_IDS = {
    1,   # Dairy and Egg Products
    2,   # Spices and Herbs
    4,   # Fats and Oils
    5,   # Poultry Products
    9,   # Fruits and Fruit Juices
    10,  # Pork Products
    11,  # Vegetables and Vegetable Products
    12,  # Nut and Seed Products
    13,  # Beef Products
    15,  # Finfish and Shellfish Products
    16,  # Legumes and Legume Products
    17,  # Lamb, Veal, and Game Products
    20,  # Cereal Grains and Pasta
}


def load_from_zip(zip_path, filename):
    with zipfile.ZipFile(zip_path, 'r') as z:
        with z.open(filename) as f:
            return pd.read_csv(f, low_memory=False)


def process_one_source(zip_path, source_name, valid_data_types):
    """Process one USDA ZIP into a flat nutrition DataFrame."""

    # ── Load and filter foods ────────────────────────────────────────────────
    print(f"  Loading food.csv...")
    food_df = load_from_zip(zip_path, "food.csv")
    food_df = food_df[food_df['data_type'].isin(valid_data_types)]
    food_df = food_df[food_df['food_category_id'].isin(KEEP_CATEGORY_IDS)]
    food_df = food_df[['fdc_id', 'description', 'food_category_id']].copy()
    food_df = food_df.rename(columns={'description': 'food_name'})
    food_df['data_source'] = source_name
    print(f"    {len(food_df):,} food items after filtering")

    # ── Load categories ──────────────────────────────────────────────────────
    cat_df = load_from_zip(zip_path, "food_category.csv")
    cat_df = cat_df[['id', 'description']].rename(
        columns={'id': 'food_category_id', 'description': 'category'}
    )
    food_df = food_df.merge(cat_df, on='food_category_id', how='left')

    # ── Load nutrition (the large file) ─────────────────────────────────────
    print(f"  Loading food_nutrient.csv...")
    fn_df = load_from_zip(zip_path, "food_nutrient.csv")
    valid_fdc_ids = set(food_df['fdc_id'])
    fn_df = fn_df[fn_df['fdc_id'].isin(valid_fdc_ids)]
    fn_df = fn_df[fn_df['nutrient_id'].isin(ALL_TARGET_IDS)]
    fn_df = fn_df[['fdc_id', 'nutrient_id', 'amount']].copy()
    fn_df['amount'] = pd.to_numeric(fn_df['amount'], errors='coerce')
    print(f"    {len(fn_df):,} nutrient records after filtering")

    # ── Handle calories from multiple IDs ────────────────────────────────────
    # Extract all calorie records from all three possible IDs
    calorie_records = fn_df[fn_df['nutrient_id'].isin(CALORIE_IDS)].copy()

    # Priority order: 2047 (Atwater General) > 1008 (Energy) > 2048 (Atwater Specific)
    # Lower priority number = preferred
    priority = {2047: 1, 1008: 2, 2048: 3}
    calorie_records['priority'] = calorie_records['nutrient_id'].map(priority)
    calorie_records = calorie_records.sort_values('priority')

    # For each food, keep only the highest-priority calorie value
    calorie_best = (
        calorie_records
        .groupby('fdc_id')
        .first()
        .reset_index()[['fdc_id', 'amount']]
        .rename(columns={'amount': 'calories'})
    )

    # ── Handle all other nutrients ───────────────────────────────────────────
    other_records = fn_df[fn_df['nutrient_id'].isin(OTHER_NUTRIENT_IDS.values())].copy()
    other_records['nutrient_col'] = other_records['nutrient_id'].map(ID_TO_COL)
    other_records = other_records.dropna(subset=['nutrient_col', 'amount'])

    # Average if multiple measurements exist for same food+nutrient
    other_records = (
        other_records
        .groupby(['fdc_id', 'nutrient_col'])['amount']
        .mean()
        .reset_index()
    )

    # Pivot long → wide
    print(f"  Pivoting to wide format...")
    nutrition_wide = other_records.pivot(
        index='fdc_id', columns='nutrient_col', values='amount'
    ).reset_index()
    nutrition_wide.columns.name = None

    # ── Merge calories back in ───────────────────────────────────────────────
    nutrition_wide = nutrition_wide.merge(calorie_best, on='fdc_id', how='left')

    # ── Merge with food info ─────────────────────────────────────────────────
    result = food_df.merge(nutrition_wide, on='fdc_id', how='inner')

    # ── Verify calorie fix worked ────────────────────────────────────────────
    zero_cal = (result['calories'].fillna(0) == 0).sum()
    print(f"  {source_name} complete: {len(result):,} items "
          f"(zero-calorie items: {zero_cal})")

    return result


def run_processor():
    print("=" * 60)
    print("NutriSync USDA Processor (Fixed Calorie Bug)")
    print("=" * 60)

    for path, name in [(FOUNDATION_ZIP, "Foundation Foods"),
                       (SR_LEGACY_ZIP, "SR Legacy")]:
        if not os.path.exists(path):
            print(f"\nERROR: {name} ZIP not found at:\n  {path}")
            return

    print(f"\n[1/5] Processing Foundation Foods...")
    foundation_df = process_one_source(
        FOUNDATION_ZIP, "Foundation", {"foundation_food"}
    )

    print(f"\n[2/5] Processing SR Legacy...")
    sr_df = process_one_source(
        SR_LEGACY_ZIP, "SR_Legacy", {"sr_legacy_food"}
    )

    print(f"\n[3/5] Combining + deduplicating...")
    combined = pd.concat([foundation_df, sr_df], ignore_index=True)
    combined['_name_lower'] = combined['food_name'].str.lower().str.strip()
    combined['_order'] = combined['data_source'].map({'Foundation': 0, 'SR_Legacy': 1})
    combined = combined.sort_values('_order')
    combined = combined.drop_duplicates(subset='_name_lower', keep='first')
    combined = combined.drop(columns=['_order', '_name_lower'])
    print(f"  After deduplication: {len(combined):,} items")

    print(f"\n[4/5] Final cleaning...")
    all_nutrition_cols = ['calories'] + list(OTHER_NUTRIENT_IDS.keys())

    # Ensure all columns exist
    for col in all_nutrition_cols:
        if col not in combined.columns:
            combined[col] = 0.0

    # Fill NaN → 0, round, clip negatives
    combined[all_nutrition_cols] = (
        combined[all_nutrition_cols]
        .fillna(0)
        .round(2)
        .clip(lower=0)
    )

    # Remove items with truly no nutrition data
    before = len(combined)
    combined = combined[
        (combined['calories'] > 0) | (combined['protein_g'] > 0)
    ]
    print(f"  Removed {before - len(combined)} items with no usable nutrition")

    # Add lowercase search column for Module 5
    combined['food_name_lower'] = combined['food_name'].str.lower().str.strip()
    combined = combined.drop(columns=['food_category_id'], errors='ignore')

    final_cols = (
        ['fdc_id', 'food_name', 'food_name_lower', 'data_source', 'category']
        + all_nutrition_cols
    )
    combined = combined[final_cols].reset_index(drop=True)

    print(f"\n[5/5] Saving...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)

    # ── Final verification ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DONE")
    print(f"{'='*60}")
    print(f"Output : {OUTPUT_PATH}")
    print(f"Total  : {len(combined):,} ingredients")

    print(f"\nCalorie fix verification:")
    zero_cal = (combined['calories'] == 0).sum()
    non_zero = (combined['calories'] > 0).sum()
    print(f"  Items with calories > 0  : {non_zero:,}")
    print(f"  Items with calories = 0  : {zero_cal} "
          f"({'✓ OK - these are genuinely zero calorie foods' if zero_cal < 50 else '⚠ Still high - investigate'})")

    print(f"\nNutrition column coverage:")
    for col in all_nutrition_cols:
        pct = (combined[col] > 0).mean() * 100
        flag = '✓' if pct > 60 else ('~' if pct > 30 else '○')
        print(f"  {flag} {col:20} {pct:5.1f}% of items have values")

    print(f"\nBy source:")
    for src, count in combined['data_source'].value_counts().items():
        print(f"  {src:15} {count:,}")

    print(f"\nBy category:")
    for cat, count in combined['category'].value_counts().items():
        print(f"  {str(cat):40} {count:,}")

    print(f"\nSample rows (should all have calories now):")
    sample = combined[combined['data_source'] == 'Foundation'].head(5)
    print(sample[['food_name', 'calories', 'protein_g', 'fat_g', 'carbs_g']].to_string())


if __name__ == "__main__":
    run_processor()

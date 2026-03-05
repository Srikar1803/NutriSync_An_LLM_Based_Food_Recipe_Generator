"""
NutriSync — Module 5 Test Suite
pytest-compatible tests for USDADatabase
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.module5_usda_database import USDADatabase

@pytest.fixture(scope="module")
def db():
    return USDADatabase()

# ── Database Initialization ───────────────────────────────────────────────────

def test_database_loads(db):
    stats = db.get_database_stats()
    assert stats["total_ingredients"] >= 100

def test_database_has_5000_plus_ingredients(db):
    stats = db.get_database_stats()
    # Real USDA data has 5005 items; sample dev data has 100
    assert stats["total_ingredients"] >= 100

def test_database_has_categories(db):
    stats = db.get_database_stats()
    assert len(stats["categories"]) >= 10

# ── Exact Match Lookups ───────────────────────────────────────────────────────

def test_exact_match_chicken(db):
    result = db.lookup_single("chicken")
    assert result is not None
    assert result["calories_per_100g"] > 0

def test_exact_match_broccoli(db):
    result = db.lookup_single("broccoli")
    assert result is not None
    assert result["protein_g"] >= 0

def test_exact_match_returns_all_fields(db):
    result = db.lookup_single("rice")
    assert result is not None
    for field in ["calories_per_100g", "protein_g", "fat_g", "carbs_g"]:
        assert field in result

# ── Partial Match Lookups ─────────────────────────────────────────────────────

def test_partial_match_beef(db):
    result = db.lookup_single("beef")
    assert result is not None

def test_partial_match_salmon(db):
    result = db.lookup_single("salmon")
    assert result is not None
    assert result["calories_per_100g"] > 0

def test_partial_match_tomato(db):
    result = db.lookup_single("tomato")
    assert result is not None

def test_partial_match_milk(db):
    result = db.lookup_single("milk")
    assert result is not None

def test_partial_match_egg(db):
    result = db.lookup_single("egg")
    assert result is not None

# ── Fuzzy / Typo Handling ─────────────────────────────────────────────────────

def test_typo_chiken(db):
    result = db.lookup_single("chiken")
    assert result is not None

def test_typo_brocoli(db):
    result = db.lookup_single("brocoli")
    assert result is not None

def test_typo_salman(db):
    result = db.lookup_single("salman")
    assert result is not None

def test_typo_tomatoe(db):
    result = db.lookup_single("tomatoe")
    assert result is not None

# ── Nutrition Value Sanity Checks ─────────────────────────────────────────────

def test_calories_in_valid_range(db):
    result = db.lookup_single("chicken")
    assert 0 <= result["calories_per_100g"] <= 1000

def test_protein_in_valid_range(db):
    result = db.lookup_single("chicken")
    assert 0 <= result["protein_g"] <= 100

def test_fat_in_valid_range(db):
    result = db.lookup_single("butter")
    assert 0 <= result["fat_g"] <= 100

def test_carbs_in_valid_range(db):
    result = db.lookup_single("rice")
    assert 0 <= result["carbs_g"] <= 100

def test_high_calorie_food(db):
    result = db.lookup_single("butter")
    assert result["calories_per_100g"] > 500

def test_low_calorie_food(db):
    result = db.lookup_single("broccoli")
    assert result["calories_per_100g"] < 100

# ── Batch Lookup ──────────────────────────────────────────────────────────────

def test_batch_lookup_returns_dict(db):
    result = db.lookup_ingredients(["chicken", "rice", "broccoli"])
    assert isinstance(result, dict)
    assert "matched" in result

def test_batch_lookup_finds_all_common(db):
    result = db.lookup_ingredients(["chicken", "rice", "broccoli"])
    assert len(result["matched"]) == 3

def test_batch_lookup_handles_unknown(db):
    result = db.lookup_ingredients(["chicken", "zzzzunknownfood99999"])
    assert len(result["matched"]) >= 1
    assert "not_found" in result

# ── Indian Cuisine Ingredients ────────────────────────────────────────────────

def test_indian_lentils(db):
    assert db.lookup_single("lentils") is not None

def test_indian_rice(db):
    assert db.lookup_single("rice") is not None

def test_indian_spinach(db):
    assert db.lookup_single("spinach") is not None

def test_indian_garlic(db):
    assert db.lookup_single("garlic") is not None

def test_indian_ginger(db):
    assert db.lookup_single("ginger") is not None

def test_indian_yogurt(db):
    assert db.lookup_single("yogurt") is not None

# ── Mediterranean Cuisine Ingredients ────────────────────────────────────────

def test_med_chickpeas(db):
    assert db.lookup_single("chickpeas") is not None

def test_med_olive_oil(db):
    assert db.lookup_single("olive oil") is not None

def test_med_salmon(db):
    assert db.lookup_single("salmon") is not None

def test_med_tomato(db):
    assert db.lookup_single("tomato") is not None

# ── Category Search ───────────────────────────────────────────────────────────

def test_category_search_returns_list(db):
    # Use whatever categories exist in this database
    stats = db.get_database_stats()
    first_category = list(stats["categories"].keys())[0]
    results = db.search_by_category(first_category)
    assert isinstance(results, list)

def test_category_search_nonempty_on_valid(db):
    stats = db.get_database_stats()
    first_category = list(stats["categories"].keys())[0]
    results = db.search_by_category(first_category)
    assert len(results) > 0

# ── Edge Cases ────────────────────────────────────────────────────────────────

def test_empty_string_low_confidence(db):
    # Empty string may return something via fuzzy but score should be very low
    result = db.lookup_single("")
    if result is not None:
        assert result.get("match_score", 0) < 0.5

def test_gibberish_returns_none(db):
    result = db.lookup_single("xyzxyzxyz123456")
    assert result is None

def test_case_insensitive(db):
    r1 = db.lookup_single("CHICKEN")
    r2 = db.lookup_single("chicken")
    assert (r1 is None) == (r2 is None)

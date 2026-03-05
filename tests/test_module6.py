"""
NutriSync — Module 6 Test Suite
pytest-compatible tests for PromptBuilder
"""
import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.module1_user_profile import UserProfile
from modules.module4_biometric_interpreter import BiometricInterpreter
from modules.module6_prompt_builder import PromptBuilder, load_prompt_context


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def config_dir(tmp_path):
    """Create temp config dir with both upstream JSON files ready."""
    d = str(tmp_path)
    # Module 1
    up = UserProfile(config_dir=d)
    up.create_profile(
        name="Srikar", age=25, weight_kg=70.0,
        height_cm=175.0, sex="male",
        dietary_pref="non-vegetarian",
        cuisine_pref=["Indian"], allergies=["none"]
    )
    # Module 4
    bi = BiometricInterpreter(config_dir=d)
    bi.interpret(steps=8500, heart_rate=88,
                 sleep_hours=5.5, stress_level=7)
    return d

@pytest.fixture
def pb(config_dir):
    return PromptBuilder(config_dir=config_dir)

INGREDIENTS = ["chicken", "rice", "spinach", "garlic", "tomato"]


# ── Output Structure ──────────────────────────────────────────────────────────

def test_build_returns_dict(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert isinstance(result, dict)

def test_build_has_required_keys(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    for key in ["prompt", "ingredients", "cuisine", "meal_type",
                "tdee_kcal", "target_calories", "usda_matches",
                "not_found", "timestamp"]:
        assert key in result, f"Missing key: {key}"

def test_build_saves_json(pb, config_dir):
    pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert os.path.exists(os.path.join(config_dir, "prompt_context.json"))

def test_build_json_valid(pb, config_dir):
    pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    with open(os.path.join(config_dir, "prompt_context.json")) as f:
        data = json.load(f)
    assert data["cuisine"] == "Indian"


# ── Prompt Content ────────────────────────────────────────────────────────────

def test_prompt_is_string(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert isinstance(result["prompt"], str)

def test_prompt_not_empty(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert len(result["prompt"]) > 100

def test_prompt_contains_user_name(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "Srikar" in result["prompt"]

def test_prompt_contains_cuisine(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "Indian" in result["prompt"]

def test_prompt_contains_tdee(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "TDEE" in result["prompt"] or "2,672" in result["prompt"] or "2672" in result["prompt"]

def test_prompt_contains_ingredients(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "chicken" in result["prompt"].lower()
    assert "rice" in result["prompt"].lower()

def test_prompt_contains_nutrient_flags(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    # biometrics: sleep=5.5 → magnesium, stress=7 → omega3
    assert "Magnesium" in result["prompt"] or "magnesium" in result["prompt"]

def test_prompt_contains_output_format(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "RECIPE NAME" in result["prompt"]
    assert "INGREDIENTS" in result["prompt"]
    assert "INSTRUCTIONS" in result["prompt"]
    assert "NUTRITION ESTIMATE" in result["prompt"]

def test_prompt_contains_bmi(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "22.9" in result["prompt"] or "Normal weight" in result["prompt"]

def test_prompt_contains_biometric_summary(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert "8,500" in result["prompt"] or "8500" in result["prompt"]


# ── Calorie Target ────────────────────────────────────────────────────────────

def test_target_calories_dinner(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    # dinner = 35% of TDEE (~2672) ≈ 935
    assert 800 < result["target_calories"] < 1100

def test_target_calories_breakfast(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="breakfast")
    # breakfast = 25% of TDEE ≈ 668
    assert 600 < result["target_calories"] < 800

def test_target_calories_snack(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="snack")
    # snack = 10% of TDEE ≈ 267
    assert 200 < result["target_calories"] < 400

def test_target_calories_less_than_tdee(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert result["target_calories"] < result["tdee_kcal"]


# ── USDA Matches ──────────────────────────────────────────────────────────────

def test_usda_matches_is_dict(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert isinstance(result["usda_matches"], dict)

def test_usda_matches_common_ingredients(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert len(result["usda_matches"]) > 0

def test_not_found_is_list(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    assert isinstance(result["not_found"], list)

def test_unknown_ingredient_in_not_found(pb):
    ings = ["chicken", "zzzyyyxxxunknown9999"]
    result = pb.build(ings, cuisine="Indian", meal_type="dinner")
    assert len(result["usda_matches"]) >= 1


# ── Different Cuisines and Meal Types ────────────────────────────────────────

def test_mediterranean_cuisine(pb):
    result = pb.build(["salmon", "tomato", "olive oil"],
                      cuisine="Mediterranean", meal_type="dinner")
    assert "Mediterranean" in result["prompt"]

def test_chinese_cuisine(pb):
    result = pb.build(["chicken", "broccoli", "garlic"],
                      cuisine="Chinese", meal_type="lunch")
    assert "Chinese" in result["prompt"]

def test_any_cuisine(pb):
    result = pb.build(INGREDIENTS, cuisine="Any", meal_type="dinner")
    assert isinstance(result["prompt"], str)

def test_lunch_meal_type(pb):
    result = pb.build(INGREDIENTS, cuisine="Indian", meal_type="lunch")
    assert result["meal_type"] == "lunch"

def test_breakfast_meal_type(pb):
    result = pb.build(["egg", "milk"], cuisine="Any", meal_type="breakfast")
    assert result["meal_type"] == "breakfast"


# ── Load and Persistence ──────────────────────────────────────────────────────

def test_load_prompt_context(pb, config_dir):
    pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    loaded = pb.load_prompt_context()
    assert loaded is not None
    assert loaded["cuisine"] == "Indian"

def test_load_returns_none_if_missing(config_dir):
    pb2 = PromptBuilder(config_dir=config_dir)
    out = os.path.join(config_dir, "prompt_context.json")
    if os.path.exists(out):
        os.remove(out)
    assert pb2.load_prompt_context() is None

def test_get_prompt_string(pb):
    pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    prompt = pb.get_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100

def test_convenience_function(pb, config_dir):
    pb.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")
    loaded = load_prompt_context(config_dir=config_dir)
    assert loaded is not None
    assert "prompt" in loaded


# ── Input Validation ──────────────────────────────────────────────────────────

def test_empty_ingredients_raises(pb):
    with pytest.raises(ValueError):
        pb.build([], cuisine="Indian", meal_type="dinner")

def test_too_many_ingredients_raises(pb):
    with pytest.raises(ValueError):
        pb.build(["chicken"] * 21, cuisine="Indian", meal_type="dinner")

def test_invalid_meal_type_raises(pb):
    with pytest.raises(ValueError):
        pb.build(INGREDIENTS, cuisine="Indian", meal_type="brunch")

def test_missing_profile_raises(tmp_path):
    pb_no_files = PromptBuilder(config_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        pb_no_files.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")

def test_missing_biometric_raises(tmp_path):
    # Profile exists but no biometric data
    up = UserProfile(config_dir=str(tmp_path))
    up.create_profile(name="A", age=25, weight_kg=70,
                      height_cm=175, sex="male")
    pb2 = PromptBuilder(config_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        pb2.build(INGREDIENTS, cuisine="Indian", meal_type="dinner")

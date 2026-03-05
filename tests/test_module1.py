"""
NutriSync — Module 1 Test Suite
pytest-compatible tests for UserProfile
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.module1_user_profile import (
    UserProfile, load_user_profile, compute_bmi, compute_bmr
)

# ─── Fixture: fresh profile instance pointing to a temp dir ──────────────────
@pytest.fixture
def profile(tmp_path):
    return UserProfile(config_dir=str(tmp_path))

@pytest.fixture
def created_profile(tmp_path):
    up = UserProfile(config_dir=str(tmp_path))
    up.create_profile(
        name="Srikar", age=25, weight_kg=70.0, height_cm=175.0,
        sex="male", dietary_pref="non-vegetarian",
        cuisine_pref=["Indian", "Mediterranean"], allergies=["none"]
    )
    return up


# ── Profile Creation ──────────────────────────────────────────────────────────

def test_create_profile_returns_dict(profile):
    result = profile.create_profile(
        name="Srikar", age=25, weight_kg=70.0,
        height_cm=175.0, sex="male"
    )
    assert isinstance(result, dict)

def test_create_profile_has_required_keys(profile):
    result = profile.create_profile(
        name="Srikar", age=25, weight_kg=70.0,
        height_cm=175.0, sex="male"
    )
    for key in ["name","age","weight_kg","height_cm","sex",
                "bmi","bmi_category","bmr_kcal","base_calories",
                "dietary_pref","cuisine_pref","allergies","created_at"]:
        assert key in result, f"Missing key: {key}"

def test_create_profile_saves_to_disk(profile):
    profile.create_profile(name="Srikar", age=25, weight_kg=70.0,
                           height_cm=175.0, sex="male")
    assert os.path.exists(profile.config_path)

def test_create_profile_male(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=70,
                                    height_cm=175, sex="male")
    assert result["sex"] == "male"
    assert result["bmr_kcal"] > 0

def test_create_profile_female(profile):
    result = profile.create_profile(name="B", age=30, weight_kg=60,
                                    height_cm=165, sex="female")
    assert result["sex"] == "female"
    assert result["bmr_kcal"] > 0

def test_create_profile_stores_correct_name(profile):
    result = profile.create_profile(name="  Srikar  ", age=25,
                                    weight_kg=70, height_cm=175, sex="male")
    assert result["name"] == "Srikar"


# ── BMI Computation ───────────────────────────────────────────────────────────

def test_bmi_underweight(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=45,
                                    height_cm=175, sex="male")
    assert result["bmi_category"] == "Underweight"

def test_bmi_normal(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=70,
                                    height_cm=175, sex="male")
    assert result["bmi_category"] == "Normal weight"

def test_bmi_overweight(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=85,
                                    height_cm=175, sex="male")
    assert result["bmi_category"] == "Overweight"

def test_bmi_obese(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=110,
                                    height_cm=175, sex="male")
    assert "Obese" in result["bmi_category"]

def test_bmi_value_correct(profile):
    # 70kg / (1.75m)^2 = 22.86
    result = profile.create_profile(name="A", age=25, weight_kg=70,
                                    height_cm=175, sex="male")
    assert abs(result["bmi"] - 22.9) < 0.2

def test_standalone_compute_bmi():
    result = compute_bmi(70, 175)
    assert "bmi" in result
    assert "bmi_category" in result
    assert result["bmi_category"] == "Normal weight"


# ── BMR Computation ───────────────────────────────────────────────────────────

def test_bmr_male_positive(profile):
    result = profile.create_profile(name="A", age=25, weight_kg=70,
                                    height_cm=175, sex="male")
    assert result["bmr_kcal"] > 1000

def test_bmr_female_positive(profile):
    result = profile.create_profile(name="B", age=30, weight_kg=60,
                                    height_cm=165, sex="female")
    assert result["bmr_kcal"] > 1000

def test_bmr_male_higher_than_female_same_stats(profile):
    # For same age/weight/height, male BMR should be higher
    male   = compute_bmr(70, 175, 25, "male")
    female = compute_bmr(70, 175, 25, "female")
    assert male > female

def test_bmr_decreases_with_age():
    young = compute_bmr(70, 175, 25, "male")
    old   = compute_bmr(70, 175, 55, "male")
    assert young > old

def test_bmr_increases_with_weight():
    light  = compute_bmr(60, 175, 25, "male")
    heavy  = compute_bmr(90, 175, 25, "male")
    assert heavy > light

def test_standalone_compute_bmr():
    bmr = compute_bmr(70, 175, 25, "male")
    assert isinstance(bmr, float)
    assert bmr > 0


# ── Load and Update ───────────────────────────────────────────────────────────

def test_load_profile(created_profile):
    loaded = created_profile.load_profile()
    assert loaded is not None
    assert loaded["name"] == "Srikar"

def test_load_profile_returns_none_if_missing(profile):
    result = profile.load_profile()
    assert result is None

def test_profile_exists_true(created_profile):
    assert created_profile.profile_exists() is True

def test_profile_exists_false(profile):
    assert profile.profile_exists() is False

def test_update_weight(created_profile):
    updated = created_profile.update_profile(weight_kg=75.0)
    assert updated["weight_kg"] == 75.0
    # BMI and BMR should be recomputed
    assert updated["bmi"] != 22.9

def test_update_dietary_pref(created_profile):
    updated = created_profile.update_profile(dietary_pref="vegetarian")
    assert updated["dietary_pref"] == "vegetarian"

def test_update_saves_to_disk(created_profile):
    created_profile.update_profile(weight_kg=80.0)
    loaded = created_profile.load_profile()
    assert loaded["weight_kg"] == 80.0


# ── Input Validation ──────────────────────────────────────────────────────────

def test_invalid_age_too_low(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=5, weight_kg=70,
                               height_cm=175, sex="male")

def test_invalid_age_too_high(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=150, weight_kg=70,
                               height_cm=175, sex="male")

def test_invalid_weight_too_low(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=25, weight_kg=10,
                               height_cm=175, sex="male")

def test_invalid_height_too_low(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=25, weight_kg=70,
                               height_cm=50, sex="male")

def test_invalid_sex(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=25, weight_kg=70,
                               height_cm=175, sex="alien")

def test_invalid_dietary_pref(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="A", age=25, weight_kg=70,
                               height_cm=175, sex="male",
                               dietary_pref="carnivore")

def test_empty_name(profile):
    with pytest.raises(ValueError):
        profile.create_profile(name="", age=25, weight_kg=70,
                               height_cm=175, sex="male")


# ── Convenience Functions ─────────────────────────────────────────────────────

def test_load_user_profile_function(tmp_path):
    up = UserProfile(config_dir=str(tmp_path))
    up.create_profile(name="Test", age=25, weight_kg=70,
                      height_cm=175, sex="male")
    loaded = load_user_profile(config_dir=str(tmp_path))
    assert loaded is not None
    assert loaded["name"] == "Test"

def test_get_summary(created_profile):
    summary = created_profile.get_summary()
    assert "Srikar" in summary
    assert "BMI" in summary
    assert "BMR" in summary

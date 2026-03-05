"""
NutriSync — Module 4 Test Suite
pytest-compatible tests for BiometricInterpreter
"""
import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.module1_user_profile import UserProfile
from modules.module4_biometric_interpreter import (
    BiometricInterpreter, load_interpreted_data
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def config_dir(tmp_path):
    """Create a temp config dir with a valid user_profile.json."""
    up = UserProfile(config_dir=str(tmp_path))
    up.create_profile(
        name="Srikar", age=25, weight_kg=70.0,
        height_cm=175.0, sex="male",
        dietary_pref="non-vegetarian",
        cuisine_pref=["Indian"], allergies=["none"]
    )
    return str(tmp_path)

@pytest.fixture
def bi(config_dir):
    return BiometricInterpreter(config_dir=config_dir)


# ── Basic Output Structure ────────────────────────────────────────────────────

def test_interpret_returns_dict(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert isinstance(result, dict)

def test_interpret_has_required_keys(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    for key in ["activity_level", "tdee_kcal", "steps", "heart_rate_bpm",
                "sleep_hours", "stress_level", "spo2_pct",
                "nutrient_flags", "flag_reasons",
                "biometric_summary", "timestamp"]:
        assert key in result, f"Missing key: {key}"

def test_interpret_saves_json(bi, config_dir):
    bi.interpret(steps=8000, heart_rate=85, sleep_hours=7.0, stress_level=4)
    assert os.path.exists(os.path.join(config_dir, "interpreted_data.json"))

def test_interpret_json_is_valid(bi, config_dir):
    bi.interpret(steps=8000, heart_rate=85, sleep_hours=7.0, stress_level=4)
    with open(os.path.join(config_dir, "interpreted_data.json")) as f:
        data = json.load(f)
    assert data["steps"] == 8000


# ── Activity Classification ───────────────────────────────────────────────────

def test_activity_sedentary(bi):
    result = bi.interpret(steps=3000, heart_rate=70,
                          sleep_hours=7.0, stress_level=3)
    assert result["activity_level"] == "Sedentary"

def test_activity_active(bi):
    result = bi.interpret(steps=7000, heart_rate=85,
                          sleep_hours=7.0, stress_level=3)
    assert result["activity_level"] == "Active"

def test_activity_highly_active(bi):
    result = bi.interpret(steps=12000, heart_rate=95,
                          sleep_hours=7.0, stress_level=3)
    assert result["activity_level"] == "Highly Active"

def test_activity_boundary_6000(bi):
    result = bi.interpret(steps=6000, heart_rate=80,
                          sleep_hours=7.0, stress_level=3)
    assert result["activity_level"] == "Active"

def test_activity_boundary_10000(bi):
    result = bi.interpret(steps=10000, heart_rate=90,
                          sleep_hours=7.0, stress_level=3)
    assert result["activity_level"] == "Highly Active"


# ── TDEE Computation ──────────────────────────────────────────────────────────

def test_tdee_positive(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert result["tdee_kcal"] > 0

def test_tdee_highly_active_greater_than_sedentary(bi):
    sedentary    = bi.interpret(steps=2000, heart_rate=65,
                                sleep_hours=7.0, stress_level=3)["tdee_kcal"]
    highly_active = bi.interpret(steps=12000, heart_rate=100,
                                 sleep_hours=7.0, stress_level=3)["tdee_kcal"]
    assert highly_active > sedentary

def test_tdee_sedentary_multiplier(bi):
    # Sedentary: TDEE = BMR × 1.2, BMR ≈ 1724
    result = bi.interpret(steps=2000, heart_rate=65,
                          sleep_hours=7.0, stress_level=3)
    assert 2000 < result["tdee_kcal"] < 2200

def test_tdee_highly_active_multiplier(bi):
    # Highly Active: TDEE = BMR × 1.725, BMR ≈ 1724
    result = bi.interpret(steps=12000, heart_rate=100,
                          sleep_hours=7.0, stress_level=3)
    assert result["tdee_kcal"] > 2800


# ── Nutrient Flags ────────────────────────────────────────────────────────────

def test_flag_protein_active(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert result["nutrient_flags"]["prioritise_protein"] is True

def test_flag_protein_sedentary(bi):
    result = bi.interpret(steps=2000, heart_rate=65,
                          sleep_hours=7.0, stress_level=3)
    assert result["nutrient_flags"]["prioritise_protein"] is False

def test_flag_magnesium_low_sleep(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=5.0, stress_level=3)
    assert result["nutrient_flags"]["prioritise_magnesium"] is True

def test_flag_magnesium_good_sleep(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.5, stress_level=3)
    assert result["nutrient_flags"]["prioritise_magnesium"] is False

def test_flag_omega3_high_stress(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.0, stress_level=8)
    assert result["nutrient_flags"]["prioritise_omega3"] is True

def test_flag_omega3_low_stress(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.0, stress_level=3)
    assert result["nutrient_flags"]["prioritise_omega3"] is False

def test_flag_iron_low_spo2(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.0, stress_level=3, spo2_pct=93.0)
    assert result["nutrient_flags"]["prioritise_iron"] is True

def test_flag_iron_normal_spo2(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.0, stress_level=3, spo2_pct=98.0)
    assert result["nutrient_flags"]["prioritise_iron"] is False

def test_flag_carbs_highly_active(bi):
    result = bi.interpret(steps=12000, heart_rate=100,
                          sleep_hours=7.0, stress_level=3)
    assert result["nutrient_flags"]["prioritise_carbs"] is True

def test_flag_reasons_populated(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=5.0, stress_level=8)
    assert len(result["flag_reasons"]) > 0
    assert "prioritise_magnesium" in result["flag_reasons"]
    assert "prioritise_omega3" in result["flag_reasons"]


# ── Biometric Summary ─────────────────────────────────────────────────────────

def test_summary_is_string(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert isinstance(result["biometric_summary"], str)

def test_summary_not_empty(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert len(result["biometric_summary"]) > 20

def test_summary_contains_tdee(bi):
    result = bi.interpret(steps=8000, heart_rate=85,
                          sleep_hours=7.0, stress_level=4)
    assert "kcal" in result["biometric_summary"]

def test_summary_mentions_low_sleep(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=5.0, stress_level=3)
    assert "5.0" in result["biometric_summary"] or "short" in result["biometric_summary"]

def test_summary_mentions_high_stress(bi):
    result = bi.interpret(steps=5000, heart_rate=75,
                          sleep_hours=7.0, stress_level=9)
    assert "high" in result["biometric_summary"].lower() or "9" in result["biometric_summary"]


# ── Load and Persistence ──────────────────────────────────────────────────────

def test_load_interpreted_data(bi, config_dir):
    bi.interpret(steps=8000, heart_rate=85,
                 sleep_hours=7.0, stress_level=4)
    loaded = bi.load_interpreted_data()
    assert loaded is not None
    assert loaded["steps"] == 8000

def test_load_returns_none_if_missing(config_dir):
    bi2 = BiometricInterpreter(config_dir=config_dir)
    # Don't call interpret — file shouldn't exist
    import shutil
    out = os.path.join(config_dir, "interpreted_data.json")
    if os.path.exists(out):
        os.remove(out)
    assert bi2.load_interpreted_data() is None

def test_get_active_flags(bi):
    bi.interpret(steps=5000, heart_rate=75,
                 sleep_hours=5.0, stress_level=8)
    active = bi.get_active_flags()
    assert isinstance(active, list)
    assert "prioritise_magnesium" in active
    assert "prioritise_omega3" in active

def test_convenience_function(bi, config_dir):
    bi.interpret(steps=8000, heart_rate=85,
                 sleep_hours=7.0, stress_level=4)
    loaded = load_interpreted_data(config_dir=config_dir)
    assert loaded is not None
    assert "tdee_kcal" in loaded


# ── Input Validation ──────────────────────────────────────────────────────────

def test_invalid_steps_negative(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=-100, heart_rate=85,
                     sleep_hours=7.0, stress_level=4)

def test_invalid_steps_too_high(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=99999, heart_rate=85,
                     sleep_hours=7.0, stress_level=4)

def test_invalid_heart_rate(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=8000, heart_rate=300,
                     sleep_hours=7.0, stress_level=4)

def test_invalid_sleep_negative(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=8000, heart_rate=85,
                     sleep_hours=-1, stress_level=4)

def test_invalid_stress_zero(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=8000, heart_rate=85,
                     sleep_hours=7.0, stress_level=0)

def test_invalid_stress_eleven(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=8000, heart_rate=85,
                     sleep_hours=7.0, stress_level=11)

def test_invalid_spo2_too_low(bi):
    with pytest.raises(ValueError):
        bi.interpret(steps=8000, heart_rate=85,
                     sleep_hours=7.0, stress_level=4, spo2_pct=70.0)

def test_missing_profile_raises(tmp_path):
    bi_no_profile = BiometricInterpreter(config_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        bi_no_profile.interpret(steps=8000, heart_rate=85,
                                sleep_hours=7.0, stress_level=4)

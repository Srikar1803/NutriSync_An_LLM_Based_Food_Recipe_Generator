"""
NutriSync — Module 1: User Profile & BMI
=========================================
Responsibilities:
  - Collect and validate user profile (age, weight, height, sex, preferences)
  - Compute BMI and BMI category
  - Compute Basal Metabolic Rate (BMR) using Harris-Benedict equation
  - Compute base daily calorie needs (before activity adjustment)
  - Store profile to JSON for use by downstream modules

Used by:
  - Module 4 (Biometric Interpreter) — receives this profile to compute TDEE
  - Module 6 (Prompt Builder)        — receives dietary preferences

Output format (returned as dict and saved to config/user_profile.json):
{
    "name"              : "Srikar",
    "age"               : 25,
    "weight_kg"         : 70.0,
    "height_cm"         : 175.0,
    "sex"               : "male",
    "dietary_pref"      : "non-vegetarian",
    "cuisine_pref"      : ["Indian", "Mediterranean"],
    "allergies"         : ["nuts"],
    "bmi"               : 22.9,
    "bmi_category"      : "Normal weight",
    "bmr_kcal"          : 1724.0,
    "base_calories"     : 1724.0,
    "created_at"        : "2026-02-26T10:00:00"
}
"""

import os
import json
import math
from datetime import datetime


# ─── Constants ────────────────────────────────────────────────────────────────

BMI_CATEGORIES = [
    (0,    18.5, "Underweight"),
    (18.5, 25.0, "Normal weight"),
    (25.0, 30.0, "Overweight"),
    (30.0, 35.0, "Obese (Class I)"),
    (35.0, 40.0, "Obese (Class II)"),
    (40.0, 999,  "Obese (Class III)"),
]

DIETARY_OPTIONS = [
    "non-vegetarian",
    "vegetarian",
    "vegan",
    "pescatarian",
    "keto",
    "gluten-free",
]

CUISINE_OPTIONS = [
    "Indian",
    "Mediterranean",
    "Chinese",
    "Italian",
    "Mexican",
    "Japanese",
    "American",
    "Thai",
    "Middle Eastern",
    "Korean",
]

COMMON_ALLERGIES = [
    "nuts",
    "dairy",
    "gluten",
    "eggs",
    "shellfish",
    "soy",
    "none",
]


# ─── Core Class ───────────────────────────────────────────────────────────────

class UserProfile:
    """
    Handles user profile creation, validation, BMI/BMR computation,
    and persistence.
    """

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Default: project_root/config/
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config"
            )
        os.makedirs(config_dir, exist_ok=True)
        self.config_path = os.path.join(config_dir, "user_profile.json")
        self.profile = None

    # ── Public API ────────────────────────────────────────────────────────────

    def create_profile(
        self,
        name: str,
        age: int,
        weight_kg: float,
        height_cm: float,
        sex: str,
        dietary_pref: str = "non-vegetarian",
        cuisine_pref: list = None,
        allergies: list = None,
    ) -> dict:
        """
        Create a new user profile with full validation and BMI/BMR computation.

        Args:
            name         : User's name (1–50 characters)
            age          : Age in years (10–120)
            weight_kg    : Weight in kilograms (20–300)
            height_cm    : Height in centimetres (100–250)
            sex          : "male" or "female"
            dietary_pref : One of DIETARY_OPTIONS
            cuisine_pref : List of preferred cuisines
            allergies    : List of food allergies

        Returns:
            Complete profile dict including BMI, BMI category, BMR

        Raises:
            ValueError if any input fails validation
        """

        # ── Validate all inputs first ──────────────────────────────────────
        self._validate_name(name)
        self._validate_age(age)
        self._validate_weight(weight_kg)
        self._validate_height(height_cm)
        self._validate_sex(sex)
        self._validate_dietary_pref(dietary_pref)

        cuisine_pref = cuisine_pref or ["Indian"]
        allergies    = allergies    or ["none"]

        # ── Compute BMI ────────────────────────────────────────────────────
        bmi          = self._compute_bmi(weight_kg, height_cm)
        bmi_category = self._get_bmi_category(bmi)

        # ── Compute BMR (Harris-Benedict, 2nd revision) ────────────────────
        # Male  : 88.362 + (13.397 × kg) + (4.799 × cm) − (5.677 × age)
        # Female: 447.593 + (9.247 × kg) + (3.098 × cm) − (4.330 × age)
        bmr = self._compute_bmr(weight_kg, height_cm, age, sex)

        # ── Assemble profile ───────────────────────────────────────────────
        self.profile = {
            "name"          : name.strip(),
            "age"           : int(age),
            "weight_kg"     : round(float(weight_kg), 1),
            "height_cm"     : round(float(height_cm), 1),
            "sex"           : sex.lower().strip(),
            "dietary_pref"  : dietary_pref.lower().strip(),
            "cuisine_pref"  : cuisine_pref,
            "allergies"     : allergies,
            "bmi"           : round(bmi, 1),
            "bmi_category"  : bmi_category,
            "bmr_kcal"      : round(bmr, 1),
            "base_calories" : round(bmr, 1),
            "created_at"    : datetime.now().isoformat(timespec="seconds"),
        }

        self._save_profile()
        return self.profile

    def load_profile(self) -> dict:
        """
        Load existing profile from disk.

        Returns:
            Profile dict, or None if no profile exists yet
        """
        if not os.path.exists(self.config_path):
            return None
        with open(self.config_path, "r") as f:
            self.profile = json.load(f)
        return self.profile

    def update_profile(self, **kwargs) -> dict:
        """
        Update specific fields in an existing profile.
        Re-computes BMI and BMR if weight, height, age, or sex changes.

        Example:
            profile.update_profile(weight_kg=72.5, dietary_pref="vegetarian")
        """
        if self.profile is None:
            self.profile = self.load_profile()
        if self.profile is None:
            raise RuntimeError("No profile exists. Call create_profile() first.")

        # Apply updates
        for key, value in kwargs.items():
            if key in self.profile:
                self.profile[key] = value

        # Re-compute BMI and BMR if any of the relevant fields changed
        recompute_fields = {"weight_kg", "height_cm", "age", "sex"}
        if recompute_fields & set(kwargs.keys()):
            bmi = self._compute_bmi(self.profile["weight_kg"], self.profile["height_cm"])
            bmr = self._compute_bmr(
                self.profile["weight_kg"], self.profile["height_cm"],
                self.profile["age"],       self.profile["sex"]
            )
            self.profile["bmi"]          = round(bmi, 1)
            self.profile["bmi_category"] = self._get_bmi_category(bmi)
            self.profile["bmr_kcal"]     = round(bmr, 1)
            self.profile["base_calories"]= round(bmr, 1)

        self.profile["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_profile()
        return self.profile

    def get_summary(self) -> str:
        """
        Return a human-readable summary of the current profile.
        """
        if self.profile is None:
            self.load_profile()
        if self.profile is None:
            return "No profile found. Please create a profile first."

        p = self.profile
        lines = [
            "─" * 45,
            f"  User Profile — {p['name']}",
            "─" * 45,
            f"  Age          : {p['age']} years",
            f"  Weight       : {p['weight_kg']} kg",
            f"  Height       : {p['height_cm']} cm",
            f"  Sex          : {p['sex'].title()}",
            f"  BMI          : {p['bmi']}  ({p['bmi_category']})",
            f"  BMR          : {p['bmr_kcal']} kcal/day (at rest)",
            f"  Diet         : {p['dietary_pref'].title()}",
            f"  Cuisines     : {', '.join(p['cuisine_pref'])}",
            f"  Allergies    : {', '.join(p['allergies'])}",
            "─" * 45,
        ]
        return "\n".join(lines)

    def profile_exists(self) -> bool:
        return os.path.exists(self.config_path)

    # ── Computation Methods ───────────────────────────────────────────────────

    @staticmethod
    def _compute_bmi(weight_kg: float, height_cm: float) -> float:
        height_m = height_cm / 100.0
        return weight_kg / (height_m ** 2)

    @staticmethod
    def _get_bmi_category(bmi: float) -> str:
        for lo, hi, label in BMI_CATEGORIES:
            if lo <= bmi < hi:
                return label
        return "Unknown"

    @staticmethod
    def _compute_bmr(weight_kg: float, height_cm: float,
                     age: int, sex: str) -> float:
        if sex.lower() == "male":
            return 88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age)
        else:
            return 447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age)

    # ── Validation Methods ────────────────────────────────────────────────────

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str) or len(name.strip()) < 1:
            raise ValueError("Name must be a non-empty string.")
        if len(name.strip()) > 50:
            raise ValueError("Name must be 50 characters or fewer.")

    @staticmethod
    def _validate_age(age):
        if not isinstance(age, (int, float)) or not (10 <= int(age) <= 120):
            raise ValueError(f"Age must be between 10 and 120. Got: {age}")

    @staticmethod
    def _validate_weight(weight_kg):
        if not isinstance(weight_kg, (int, float)) or not (20 <= weight_kg <= 300):
            raise ValueError(f"Weight must be between 20 and 300 kg. Got: {weight_kg}")

    @staticmethod
    def _validate_height(height_cm):
        if not isinstance(height_cm, (int, float)) or not (100 <= height_cm <= 250):
            raise ValueError(f"Height must be between 100 and 250 cm. Got: {height_cm}")

    @staticmethod
    def _validate_sex(sex):
        if sex.lower().strip() not in ("male", "female"):
            raise ValueError(f"Sex must be 'male' or 'female'. Got: {sex}")

    @staticmethod
    def _validate_dietary_pref(dietary_pref):
        if dietary_pref.lower().strip() not in DIETARY_OPTIONS:
            raise ValueError(
                f"dietary_pref must be one of {DIETARY_OPTIONS}. Got: {dietary_pref}"
            )

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_profile(self):
        with open(self.config_path, "w") as f:
            json.dump(self.profile, f, indent=2)


# ─── Standalone helper functions (used by other modules) ─────────────────────

def load_user_profile(config_dir: str = None) -> dict:
    """
    Convenience function — load profile without instantiating class.
    Used by Module 4 and Module 6 to read the profile.
    Returns None if no profile exists.
    """
    up = UserProfile(config_dir)
    return up.load_profile()


def compute_bmi(weight_kg: float, height_cm: float) -> dict:
    """
    Standalone BMI calculator. Returns bmi value + category.
    """
    bmi      = UserProfile._compute_bmi(weight_kg, height_cm)
    category = UserProfile._get_bmi_category(bmi)
    return {"bmi": round(bmi, 1), "bmi_category": category}


def compute_bmr(weight_kg: float, height_cm: float,
                age: int, sex: str) -> float:
    """
    Standalone BMR calculator using Harris-Benedict equation.
    Returns BMR in kcal/day.
    """
    return round(UserProfile._compute_bmr(weight_kg, height_cm, age, sex), 1)

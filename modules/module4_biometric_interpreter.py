"""
NutriSync — Module 4: Biometric Interpreter
=============================================
Responsibilities:
  - Accept biometric inputs (steps, heart rate, sleep, stress, SpO2)
  - Classify activity level from step count + heart rate
  - Compute TDEE (Total Daily Energy Expenditure) using BMR from Module 1
  - Generate nutrient flags based on biometric signals
  - Produce a plain-English biometric summary for the LLM prompt
  - Save output to config/interpreted_data.json

Input:  config/user_profile.json  (written by Module 1)
Output: config/interpreted_data.json

Output format:
{
    "activity_level"    : "Active",
    "tdee_kcal"         : 2672.0,
    "steps"             : 8500,
    "heart_rate_bpm"    : 88,
    "sleep_hours"       : 5.5,
    "stress_level"      : 7,
    "spo2_pct"          : 97.0,
    "nutrient_flags"    : {
        "prioritise_protein"  : true,
        "prioritise_magnesium": true,
        "prioritise_iron"     : false,
        "prioritise_omega3"   : true,
        "prioritise_carbs"    : false
    },
    "flag_reasons"      : {
        "prioritise_magnesium": "Sleep < 6 hrs — magnesium aids sleep quality",
        "prioritise_omega3"   : "Stress >= 7 — omega-3 reduces cortisol"
    },
    "biometric_summary" : "You had a moderately active day (8,500 steps). ...",
    "timestamp"         : "2026-02-26T10:00:00"
}

Used by:
  - Module 6 (Prompt Builder) — reads interpreted_data.json
"""

import os
import json
from datetime import datetime


# ─── Activity classification thresholds ──────────────────────────────────────
# Based on WHO physical activity guidelines + step count research

ACTIVITY_THRESHOLDS = {
    "Highly Active" : 10000,   # steps/day
    "Active"        : 6000,
    "Sedentary"     : 0,
}

# Activity multipliers for TDEE = BMR × multiplier  (Harris-Benedict)
ACTIVITY_MULTIPLIERS = {
    "Sedentary"     : 1.2,
    "Active"        : 1.55,
    "Highly Active" : 1.725,
}

# ─── Nutrient flag thresholds ─────────────────────────────────────────────────
# Each flag maps a biometric condition → a nutrient to prioritise in the recipe

FLAG_RULES = [
    # (flag_name,            condition_fn,                          reason)
    ("prioritise_protein",
     lambda b: b["activity_level"] in ("Active", "Highly Active"),
     "Active lifestyle — higher protein supports muscle repair"),

    ("prioritise_carbs",
     lambda b: b["activity_level"] == "Highly Active",
     "High intensity activity — complex carbs replenish glycogen"),

    ("prioritise_magnesium",
     lambda b: b["sleep_hours"] < 6.0,
     "Sleep < 6 hrs — magnesium aids sleep quality and muscle relaxation"),

    ("prioritise_omega3",
     lambda b: b["stress_level"] >= 7,
     "Stress >= 7/10 — omega-3 fatty acids help reduce cortisol"),

    ("prioritise_iron",
     lambda b: b["spo2_pct"] < 95.0,
     "SpO2 < 95% — iron supports haemoglobin and oxygen transport"),

    ("prioritise_vitamin_c",
     lambda b: b["stress_level"] >= 8,
     "High stress >= 8/10 — vitamin C is depleted under chronic stress"),

    ("prioritise_potassium",
     lambda b: b["steps"] >= 10000,
     "High step count — potassium replaces electrolytes lost through sweat"),
]


# ─── Core Class ───────────────────────────────────────────────────────────────

class BiometricInterpreter:
    """
    Interprets raw biometric signals into actionable nutritional context
    for the LLM prompt.
    """

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config"
            )
        os.makedirs(config_dir, exist_ok=True)
        self.config_dir        = config_dir
        self.profile_path      = os.path.join(config_dir, "user_profile.json")
        self.output_path       = os.path.join(config_dir, "interpreted_data.json")
        self.user_profile      = None
        self.interpreted_data  = None

    # ── Public API ────────────────────────────────────────────────────────────

    def interpret(
        self,
        steps        : int,
        heart_rate   : float,
        sleep_hours  : float,
        stress_level : int,
        spo2_pct     : float = 98.0,
    ) -> dict:
        """
        Main entry point. Takes raw biometric values, returns full
        interpreted context dict and saves to interpreted_data.json.

        Args:
            steps        : Daily step count (0 – 50,000)
            heart_rate   : Resting or average heart rate in BPM (30 – 220)
            sleep_hours  : Hours of sleep last night (0 – 14)
            stress_level : Self-reported stress score 1–10
            spo2_pct     : Blood oxygen saturation % (85 – 100)

        Returns:
            interpreted_data dict
        """
        # Validate inputs
        self._validate_inputs(steps, heart_rate, sleep_hours,
                               stress_level, spo2_pct)

        # Load user profile (needed for BMR)
        self._load_user_profile()

        # Build working biometric dict
        biometrics = {
            "steps"          : int(steps),
            "heart_rate_bpm" : round(float(heart_rate), 1),
            "sleep_hours"    : round(float(sleep_hours), 2),
            "stress_level"   : int(stress_level),
            "spo2_pct"       : round(float(spo2_pct), 1),
        }

        # Classify activity
        activity_level = self._classify_activity(steps, heart_rate)
        biometrics["activity_level"] = activity_level

        # Compute TDEE
        tdee = self._compute_tdee(activity_level)

        # Generate nutrient flags
        flags, flag_reasons = self._generate_flags(biometrics)

        # Generate human-readable summary
        summary = self._build_summary(biometrics, activity_level, tdee, flags)

        # Assemble final output
        self.interpreted_data = {
            "activity_level"   : activity_level,
            "tdee_kcal"        : tdee,
            "steps"            : biometrics["steps"],
            "heart_rate_bpm"   : biometrics["heart_rate_bpm"],
            "sleep_hours"      : biometrics["sleep_hours"],
            "stress_level"     : biometrics["stress_level"],
            "spo2_pct"         : biometrics["spo2_pct"],
            "nutrient_flags"   : flags,
            "flag_reasons"     : flag_reasons,
            "biometric_summary": summary,
            "timestamp"        : datetime.now().isoformat(timespec="seconds"),
        }

        self._save_output()
        return self.interpreted_data

    def load_interpreted_data(self) -> dict:
        """Load previously saved interpreted data from disk."""
        if not os.path.exists(self.output_path):
            return None
        with open(self.output_path, "r") as f:
            self.interpreted_data = json.load(f)
        return self.interpreted_data

    def get_summary(self) -> str:
        """Return the plain-English biometric summary string."""
        if self.interpreted_data is None:
            self.load_interpreted_data()
        if self.interpreted_data is None:
            return "No interpreted data found. Call interpret() first."
        return self.interpreted_data["biometric_summary"]

    def get_active_flags(self) -> list:
        """Return list of flag names that are currently True."""
        if self.interpreted_data is None:
            self.load_interpreted_data()
        if self.interpreted_data is None:
            return []
        return [k for k, v in self.interpreted_data["nutrient_flags"].items() if v]

    # ── Classification ────────────────────────────────────────────────────────

    @staticmethod
    def _classify_activity(steps: int, heart_rate: float) -> str:
        """
        Classify activity level from step count.
        Heart rate is used as a tiebreaker for borderline cases.
        """
        if steps >= ACTIVITY_THRESHOLDS["Highly Active"]:
            return "Highly Active"
        elif steps >= ACTIVITY_THRESHOLDS["Active"]:
            # Tiebreaker: elevated HR near threshold moves up
            if steps >= 8000 and heart_rate >= 100:
                return "Highly Active"
            return "Active"
        else:
            # Very low steps but high HR (e.g. illness/anxiety) stays Sedentary
            return "Sedentary"

    def _compute_tdee(self, activity_level: str) -> float:
        """TDEE = BMR × activity multiplier."""
        bmr        = self.user_profile["bmr_kcal"]
        multiplier = ACTIVITY_MULTIPLIERS[activity_level]
        return round(bmr * multiplier, 1)

    # ── Nutrient Flags ────────────────────────────────────────────────────────

    @staticmethod
    def _generate_flags(biometrics: dict) -> tuple:
        """
        Evaluate each flag rule against current biometrics.
        Returns (flags dict, flag_reasons dict).
        """
        flags        = {}
        flag_reasons = {}

        for flag_name, condition_fn, reason in FLAG_RULES:
            triggered = condition_fn(biometrics)
            flags[flag_name] = triggered
            if triggered:
                flag_reasons[flag_name] = reason

        return flags, flag_reasons

    # ── Summary Builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(biometrics: dict, activity_level: str,
                       tdee: float, flags: dict) -> str:
        """
        Build a plain-English biometric summary that goes directly
        into the LLM prompt. Concise, factual, actionable.
        """
        lines = []

        # Activity sentence
        step_desc = {
            "Sedentary"    : f"a low-activity day ({biometrics['steps']:,} steps)",
            "Active"       : f"a moderately active day ({biometrics['steps']:,} steps)",
            "Highly Active": f"a highly active day ({biometrics['steps']:,} steps)",
        }
        lines.append(f"Today was {step_desc[activity_level]}.")

        # TDEE
        lines.append(
            f"Estimated calorie need (TDEE): {tdee:,.0f} kcal."
        )

        # Sleep
        if biometrics["sleep_hours"] < 6:
            lines.append(
                f"Sleep was short at {biometrics['sleep_hours']} hours "
                f"(below the recommended 7–8 hrs)."
            )
        elif biometrics["sleep_hours"] >= 8:
            lines.append(
                f"Sleep was good at {biometrics['sleep_hours']} hours."
            )
        else:
            lines.append(
                f"Sleep was {biometrics['sleep_hours']} hours."
            )

        # Stress
        if biometrics["stress_level"] >= 7:
            lines.append(
                f"Stress level is high ({biometrics['stress_level']}/10)."
            )
        elif biometrics["stress_level"] >= 4:
            lines.append(
                f"Stress level is moderate ({biometrics['stress_level']}/10)."
            )

        # SpO2
        if biometrics["spo2_pct"] < 95:
            lines.append(
                f"Blood oxygen is low at {biometrics['spo2_pct']}% "
                f"(normal is 95–100%)."
            )

        # Active flags
        active_flags = [k for k, v in flags.items() if v]
        if active_flags:
            readable = [f.replace("prioritise_", "").replace("_", " ")
                        for f in active_flags]
            lines.append(
                f"Nutrients to prioritise in today's recipe: "
                f"{', '.join(readable)}."
            )

        return " ".join(lines)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_inputs(steps, heart_rate, sleep_hours,
                          stress_level, spo2_pct):
        if not (0 <= steps <= 50000):
            raise ValueError(f"Steps must be 0–50,000. Got: {steps}")
        if not (30 <= heart_rate <= 220):
            raise ValueError(f"Heart rate must be 30–220 BPM. Got: {heart_rate}")
        if not (0 <= sleep_hours <= 14):
            raise ValueError(f"Sleep hours must be 0–14. Got: {sleep_hours}")
        if not (1 <= stress_level <= 10):
            raise ValueError(f"Stress level must be 1–10. Got: {stress_level}")
        if not (85 <= spo2_pct <= 100):
            raise ValueError(f"SpO2 must be 85–100%. Got: {spo2_pct}")

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_user_profile(self):
        if not os.path.exists(self.profile_path):
            raise FileNotFoundError(
                f"user_profile.json not found at {self.profile_path}. "
                f"Run Module 1 first."
            )
        with open(self.profile_path, "r") as f:
            self.user_profile = json.load(f)

    def _save_output(self):
        with open(self.output_path, "w") as f:
            json.dump(self.interpreted_data, f, indent=2)


# ─── Standalone helper (used by Module 6) ────────────────────────────────────

def load_interpreted_data(config_dir: str = None) -> dict:
    """Convenience function — load interpreted_data.json without class."""
    bi = BiometricInterpreter(config_dir)
    return bi.load_interpreted_data()

"""
NutriSync — Module 6: Prompt Builder
======================================
Responsibilities:
  - Read user_profile.json       (Module 1 output)
  - Read interpreted_data.json   (Module 4 output)
  - Accept user's available ingredients + cuisine preference
  - Call Module 5 (USDADatabase) to look up nutrition for each ingredient
  - Assemble everything into a single structured prompt for the LLM
  - Save prompt_context.json for Module 7

Input:
  - config/user_profile.json
  - config/interpreted_data.json
  - ingredients : list of strings  e.g. ["chicken", "rice", "spinach"]
  - cuisine     : string           e.g. "Indian"
  - meal_type   : string           e.g. "dinner" (optional)

Output: config/prompt_context.json
{
    "prompt"         : "< full LLM prompt string >",
    "ingredients"    : ["chicken", "rice", "spinach"],
    "cuisine"        : "Indian",
    "meal_type"      : "dinner",
    "tdee_kcal"      : 2672.4,
    "target_calories": 890.0,
    "usda_matches"   : { "chicken": {...}, "rice": {...} },
    "timestamp"      : "2026-02-26T10:00:00"
}

Used by:
  - Module 7 (LLM API) — reads prompt_context.json and sends prompt to DeepSeek
"""

import os
import json
from datetime import datetime

# Module 5 import — USDA lookup engine
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.module5_usda_database import USDADatabase


# ─── Meal calorie split ───────────────────────────────────────────────────────
# What fraction of TDEE each meal represents
MEAL_CALORIE_SPLIT = {
    "breakfast": 0.25,
    "lunch"    : 0.35,
    "dinner"   : 0.35,
    "snack"    : 0.10,
}

VALID_MEAL_TYPES = list(MEAL_CALORIE_SPLIT.keys())

VALID_CUISINES = [
    "Indian", "Mediterranean", "Chinese", "Italian",
    "Mexican", "Japanese", "American", "Thai",
    "Middle Eastern", "Korean", "Any",
]


# ─── Core Class ───────────────────────────────────────────────────────────────

class PromptBuilder:
    """
    Assembles all pipeline context into a single structured LLM prompt.
    """

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config"
            )
        os.makedirs(config_dir, exist_ok=True)
        self.config_dir       = config_dir
        self.profile_path     = os.path.join(config_dir, "user_profile.json")
        self.biometric_path   = os.path.join(config_dir, "interpreted_data.json")
        self.output_path      = os.path.join(config_dir, "prompt_context.json")
        self.db               = USDADatabase()
        self.user_profile     = None
        self.biometric_data   = None
        self.prompt_context   = None

    # ── Public API ────────────────────────────────────────────────────────────

    def build(
        self,
        ingredients : list,
        cuisine     : str = "Any",
        meal_type   : str = "dinner",
    ) -> dict:
        """
        Main entry point. Builds and saves the full prompt context.

        Args:
            ingredients : List of ingredient strings the user has available
                          e.g. ["chicken breast", "rice", "spinach", "garlic"]
            cuisine     : Preferred cuisine style  e.g. "Indian"
            meal_type   : "breakfast", "lunch", "dinner", or "snack"

        Returns:
            prompt_context dict including the full prompt string

        Raises:
            FileNotFoundError if user_profile.json or interpreted_data.json missing
            ValueError on invalid inputs
        """
        # Validate
        self._validate_inputs(ingredients, cuisine, meal_type)

        # Load upstream data
        self._load_user_profile()
        self._load_biometric_data()

        # Look up USDA nutrition for each ingredient
        usda_result  = self.db.lookup_ingredients(ingredients)
        usda_matches = usda_result.get("matched", {})
        not_found    = usda_result.get("not_found", [])

        # Compute target calories for this meal
        tdee           = self.biometric_data["tdee_kcal"]
        split          = MEAL_CALORIE_SPLIT[meal_type]
        target_calories = round(tdee * split, 1)

        # Build the prompt
        prompt = self._assemble_prompt(
            ingredients, cuisine, meal_type,
            tdee, target_calories,
            usda_matches, not_found,
        )

        # Assemble and save context
        self.prompt_context = {
            "prompt"          : prompt,
            "ingredients"     : ingredients,
            "cuisine"         : cuisine,
            "meal_type"       : meal_type,
            "tdee_kcal"       : tdee,
            "target_calories" : target_calories,
            "usda_matches"    : usda_matches,
            "not_found"       : not_found,
            "timestamp"       : datetime.now().isoformat(timespec="seconds"),
        }

        self._save_output()
        return self.prompt_context

    def get_prompt(self) -> str:
        """Return just the prompt string from the last build."""
        if self.prompt_context is None:
            loaded = self._load_output()
            if loaded is None:
                return "No prompt built yet. Call build() first."
        return self.prompt_context["prompt"]

    def load_prompt_context(self) -> dict:
        """Load previously saved prompt context from disk."""
        return self._load_output()

    # ── Prompt Assembly ───────────────────────────────────────────────────────

    def _assemble_prompt(
        self,
        ingredients     : list,
        cuisine         : str,
        meal_type       : str,
        tdee            : float,
        target_calories : float,
        usda_matches    : dict,
        not_found       : list,
    ) -> str:
        """
        Build the full structured prompt that goes to the LLM.
        Every section is clearly labelled so the LLM knows exactly
        what each piece of information is.
        """

        p = self.user_profile
        b = self.biometric_data

        sections = []

        # ── System role ───────────────────────────────────────────────────────
        sections.append(
            "You are NutriSync, an expert nutritionist and chef. "
            "Your job is to generate a single, complete, practical recipe "
            "that is tailored to the user's biometric data and nutritional needs. "
            "Always respond with a recipe in the exact format specified at the end."
        )

        # ── User profile ──────────────────────────────────────────────────────
        sections.append(
            f"## USER PROFILE\n"
            f"Name           : {p['name']}\n"
            f"Age            : {p['age']} years\n"
            f"Sex            : {p['sex'].title()}\n"
            f"Weight / Height: {p['weight_kg']} kg / {p['height_cm']} cm\n"
            f"BMI            : {p['bmi']} ({p['bmi_category']})\n"
            f"Diet           : {p['dietary_pref'].title()}\n"
            f"Allergies      : {', '.join(p['allergies'])}"
        )

        # ── Today's biometrics ────────────────────────────────────────────────
        sections.append(
            f"## TODAY'S BIOMETRICS\n"
            f"{b['biometric_summary']}\n\n"
            f"Activity Level : {b['activity_level']}\n"
            f"Steps          : {b['steps']:,}\n"
            f"Heart Rate     : {b['heart_rate_bpm']} BPM\n"
            f"Sleep          : {b['sleep_hours']} hours\n"
            f"Stress         : {b['stress_level']}/10\n"
            f"SpO2           : {b['spo2_pct']}%"
        )

        # ── Calorie target ────────────────────────────────────────────────────
        sections.append(
            f"## CALORIE TARGET\n"
            f"Daily TDEE     : {tdee:,.0f} kcal\n"
            f"Meal           : {meal_type.title()}\n"
            f"Target Calories: {target_calories:,.0f} kcal "
            f"({int(MEAL_CALORIE_SPLIT[meal_type]*100)}% of TDEE)"
        )

        # ── Nutrient priorities ───────────────────────────────────────────────
        active_flags = [k for k, v in b["nutrient_flags"].items() if v]
        if active_flags:
            flag_lines = []
            for flag in active_flags:
                nutrient = flag.replace("prioritise_", "").replace("_", " ").title()
                reason   = b["flag_reasons"].get(flag, "")
                flag_lines.append(f"  - {nutrient}: {reason}")
            sections.append(
                "## NUTRIENT PRIORITIES (based on today's biometrics)\n"
                + "\n".join(flag_lines)
            )
        else:
            sections.append(
                "## NUTRIENT PRIORITIES\n"
                "No specific nutrient flags today. Focus on balanced macros."
            )

        # ── Available ingredients + USDA nutrition ────────────────────────────
        ingredient_lines = []
        for ing in ingredients:
            ing_lower = ing.lower()
            # Find match in usda_matches (keys are original user inputs)
            match = usda_matches.get(ing_lower) or usda_matches.get(ing)
            if match:
                ingredient_lines.append(
                    f"  - {ing}: {match.get('calories_per_100g', 0):.0f} kcal, "
                    f"{match.get('protein_g', 0):.1f}g protein, "
                    f"{match.get('fat_g', 0):.1f}g fat, "
                    f"{match.get('carbs_g', 0):.1f}g carbs per 100g"
                )
            else:
                ingredient_lines.append(f"  - {ing}: (nutrition data not found)")

        if not_found:
            ingredient_lines.append(
                f"\n  Note: Could not find USDA data for: {', '.join(not_found)}. "
                f"Estimate nutrition for these or substitute if needed."
            )

        sections.append(
            f"## AVAILABLE INGREDIENTS (with verified USDA nutrition per 100g)\n"
            + "\n".join(ingredient_lines)
        )

        # ── Cuisine and meal type ─────────────────────────────────────────────
        cuisine_instruction = (
            f"You MUST create a {cuisine} cuisine style {meal_type} recipe."
            if cuisine != "Any"
            else f"Create a {meal_type} recipe in any cuisine style."
        )
        sections.append(
            f"## MEAL REQUEST\n"
            f"Cuisine        : {cuisine}\n"
            f"Meal Type      : {meal_type.title()}\n"
            f"{cuisine_instruction}\n"
            f"Use ONLY the ingredients listed above. "
            f"You may include common pantry items (salt, pepper, oil, water, basic spices) "
            f"but do not add major unlisted ingredients."
        )

        # ── Output format instruction ─────────────────────────────────────────
        sections.append(
            "## OUTPUT FORMAT\n"
            "Respond in this EXACT format and no other:\n\n"
            "RECIPE NAME: <name>\n\n"
            "WHY THIS RECIPE: <1-2 sentences explaining how it addresses today's biometrics>\n\n"
            "INGREDIENTS:\n"
            "- <ingredient>: <quantity>\n"
            "(list all ingredients with quantities)\n\n"
            "INSTRUCTIONS:\n"
            "1. <step>\n"
            "(list all steps)\n\n"
            "NUTRITION ESTIMATE (per serving):\n"
            "- Calories : <number> kcal\n"
            "- Protein  : <number> g\n"
            "- Carbs    : <number> g\n"
            "- Fat      : <number> g\n\n"
            "BIOMETRIC NOTES: <1-2 sentences on which nutrient priorities this recipe addresses and why>"
        )

        # Join all sections with double newlines
        return "\n\n".join(sections)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_inputs(ingredients, cuisine, meal_type):
        if not ingredients or not isinstance(ingredients, list):
            raise ValueError("ingredients must be a non-empty list.")
        if len(ingredients) > 20:
            raise ValueError("Maximum 20 ingredients allowed.")
        if any(not isinstance(i, str) or not i.strip() for i in ingredients):
            raise ValueError("All ingredients must be non-empty strings.")
        if meal_type not in VALID_MEAL_TYPES:
            raise ValueError(
                f"meal_type must be one of {VALID_MEAL_TYPES}. Got: {meal_type}"
            )

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_user_profile(self):
        if not os.path.exists(self.profile_path):
            raise FileNotFoundError(
                f"user_profile.json not found. Run Module 1 first."
            )
        with open(self.profile_path) as f:
            self.user_profile = json.load(f)

    def _load_biometric_data(self):
        if not os.path.exists(self.biometric_path):
            raise FileNotFoundError(
                f"interpreted_data.json not found. Run Module 4 first."
            )
        with open(self.biometric_path) as f:
            self.biometric_data = json.load(f)

    def _save_output(self):
        with open(self.output_path, "w") as f:
            json.dump(self.prompt_context, f, indent=2)

    def _load_output(self) -> dict:
        if not os.path.exists(self.output_path):
            return None
        with open(self.output_path) as f:
            self.prompt_context = json.load(f)
        return self.prompt_context


# ─── Standalone helper (used by Module 7) ────────────────────────────────────

def load_prompt_context(config_dir: str = None) -> dict:
    """Convenience function — load prompt_context.json without class."""
    pb = PromptBuilder(config_dir)
    return pb.load_prompt_context()

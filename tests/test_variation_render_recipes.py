import unittest

from variation_engine.variation.render_recipes import (
    ROUND_ROBIN_RENDER_RECIPE_BY_ID,
    NumericRange,
    generate_round_robin_render_instructions,
    select_round_robin_render_recipe,
)


class RoundRobinRenderRecipesTest(unittest.TestCase):
    def test_selects_category_specific_recipe(self) -> None:
        recipe = select_round_robin_render_recipe(
            category_id="plucked_string",
            profile_id="tonal_percussive",
        )

        self.assertEqual(recipe.id, "plucked_string")

    def test_selects_profile_fallback_recipe_without_known_category(self) -> None:
        recipe = select_round_robin_render_recipe(
            category_id="unsupported_category",
            profile_id="percussive",
        )

        self.assertEqual(recipe.id, "drum_percussion")

    def test_selects_unknown_fallback_recipe_without_known_category_or_profile(self) -> None:
        recipe = select_round_robin_render_recipe(
            category_id=None,
            profile_id="unsupported_profile",
        )

        self.assertEqual(recipe.id, "unknown_conservative")

    def test_instruction_generation_is_deterministic_for_recipe_seed_and_count(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]

        first = generate_round_robin_render_instructions(
            recipe=recipe,
            count=8,
            seed=17,
        )
        second = generate_round_robin_render_instructions(
            recipe=recipe,
            count=8,
            seed=17,
        )

        self.assertEqual(first, second)

    def test_different_seed_can_produce_different_instruction_values(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]

        first = generate_round_robin_render_instructions(
            recipe=recipe,
            count=8,
            seed=17,
        )
        second = generate_round_robin_render_instructions(
            recipe=recipe,
            count=8,
            seed=18,
        )

        self.assertNotEqual(first[1:], second[1:])

    def test_instruction_values_stay_inside_recipe_ranges(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]
        instructions = generate_round_robin_render_instructions(
            recipe=recipe,
            count=8,
            seed=23,
        )

        for instruction in instructions:
            self.assertInRange(instruction.micropitch_cents, recipe.micropitch_cents)
            self.assertInRange(instruction.timing_shift_ms, recipe.timing_shift_ms)
            self.assertInRange(instruction.gain_db, recipe.gain_db)
            self.assertInRange(instruction.attack_amount, recipe.attack_amount)
            self.assertInRange(instruction.brightness_amount, recipe.brightness_amount)
            self.assertInRange(instruction.decay_amount, recipe.decay_amount)
            self.assertInRange(instruction.saturation_amount, recipe.saturation_amount)
            self.assertInRange(
                instruction.stereo_balance_amount,
                recipe.stereo_balance_amount,
            )

    def test_instruction_count_matches_requested_count(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]

        instructions = generate_round_robin_render_instructions(
            recipe=recipe,
            count=3,
            seed=0,
        )

        self.assertEqual(len(instructions), 3)
        self.assertEqual([instruction.index for instruction in instructions], [1, 2, 3])

    def assertInRange(self, value: float, value_range: NumericRange) -> None:
        self.assertGreaterEqual(value, value_range.min_value)
        self.assertLessEqual(value, value_range.max_value)


if __name__ == "__main__":
    unittest.main()

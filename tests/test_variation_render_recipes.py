import unittest

from variation_engine.variation.render_recipes import (
    ROUND_ROBIN_RENDER_RECIPE_BY_ID,
    NumericRange,
    apply_render_recipe_range_overrides,
    generate_round_robin_render_instructions,
    select_round_robin_render_recipe,
    validate_render_recipe_range_overrides,
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

    def test_selects_tonal_percussive_profile_fallback_recipe(self) -> None:
        recipe = select_round_robin_render_recipe(
            category_id=None,
            profile_id="tonal_percussive",
        )

        self.assertEqual(recipe.id, "tonal_percussive")

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

    def test_range_overrides_create_temporary_recipe_with_changed_ranges(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]

        overridden_recipe = apply_render_recipe_range_overrides(
            recipe,
            {
                "micropitch_cents": (-1.0, 1.0),
                "gain_db": (-0.25, 0.25),
                "saturation_amount": (0.0, 0.03),
            },
        )

        self.assertIsNot(overridden_recipe, recipe)
        self.assertEqual(overridden_recipe.id, recipe.id)
        self.assertEqual(overridden_recipe.micropitch_cents, NumericRange(-1.0, 1.0))
        self.assertEqual(overridden_recipe.gain_db, NumericRange(-0.25, 0.25))
        self.assertEqual(overridden_recipe.saturation_amount, NumericRange(0.0, 0.03))
        self.assertEqual(overridden_recipe.timing_shift_ms, recipe.timing_shift_ms)

    def test_range_overrides_do_not_mutate_global_recipe(self) -> None:
        recipe = ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"]
        original_micropitch = recipe.micropitch_cents

        apply_render_recipe_range_overrides(
            recipe,
            {"micropitch_cents": (-1.0, 1.0)},
        )

        self.assertEqual(recipe.micropitch_cents, original_micropitch)
        self.assertEqual(
            ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"].micropitch_cents,
            original_micropitch,
        )

    def test_invalid_range_override_values_are_rejected(self) -> None:
        invalid_overrides = [
            {"micropitch_cents": ("low", 1.0)},
            {"micropitch_cents": (float("nan"), 1.0)},
            {"micropitch_cents": (float("-inf"), 1.0)},
            {"unknown": (0.0, 1.0)},
            {"micropitch_cents": (0.0,)},
            {"saturation_amount": (-0.01, 0.05)},
        ]

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    validate_render_recipe_range_overrides(overrides)

    def test_range_override_values_outside_lab_limits_are_rejected(self) -> None:
        invalid_overrides = [
            {"micropitch_cents": (-12.1, 1.0)},
            {"timing_shift_ms": (-1.0, 10.1)},
            {"gain_db": (-3.1, 1.0)},
            {"attack_amount": (-0.51, 0.1)},
            {"brightness_amount": (-0.1, 0.51)},
            {"decay_amount": (-0.31, 0.1)},
            {"saturation_amount": (0.0, 0.21)},
            {"stereo_balance_amount": (-0.26, 0.1)},
        ]

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    validate_render_recipe_range_overrides(overrides)

    def test_range_override_min_greater_than_max_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_render_recipe_range_overrides({"micropitch_cents": (1.0, -1.0)})

    def test_instruction_generation_is_deterministic_with_range_overrides(self) -> None:
        recipe = apply_render_recipe_range_overrides(
            ROUND_ROBIN_RENDER_RECIPE_BY_ID["plucked_string"],
            {
                "micropitch_cents": (-1.0, 1.0),
                "timing_shift_ms": (-0.5, 0.5),
            },
        )

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
        for instruction in first:
            self.assertInRange(instruction.micropitch_cents, recipe.micropitch_cents)
            self.assertInRange(instruction.timing_shift_ms, recipe.timing_shift_ms)

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

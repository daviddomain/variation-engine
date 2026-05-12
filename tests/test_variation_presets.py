import dataclasses
import unittest

from variation_engine.variation.presets import (
    MAJOR_THIRDS_AROUND_SOURCE,
    SOURCE_ONLY,
    VARIATION_RULE_PRESETS,
    get_variation_rule_preset,
    get_variation_rule_preset_for_profile,
)


REQUIRED_PRESET_IDS = [
    "percussive",
    "tonal_percussive",
    "sustained_tonal",
    "sfx_texture",
    "unknown",
]


class VariationRulePresetSchemaTest(unittest.TestCase):
    def test_defines_required_default_presets_in_stable_order(self) -> None:
        self.assertEqual(
            [preset.id for preset in VARIATION_RULE_PRESETS],
            REQUIRED_PRESET_IDS,
        )

    def test_presets_are_frozen_dataclasses(self) -> None:
        for preset in VARIATION_RULE_PRESETS:
            self.assertTrue(dataclasses.is_dataclass(preset))
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(preset, "round_robin_count", 16)

    def test_every_preset_uses_default_render_dimensions(self) -> None:
        for preset in VARIATION_RULE_PRESETS:
            self.assertEqual(preset.round_robin_count, 8)
            self.assertEqual(preset.velocity_layer_count, 4)

    def test_lookup_by_preset_id_returns_matching_preset(self) -> None:
        for preset_id in REQUIRED_PRESET_IDS:
            self.assertEqual(get_variation_rule_preset(preset_id).id, preset_id)

    def test_lookup_by_profile_returns_matching_preset(self) -> None:
        for preset_id in REQUIRED_PRESET_IDS:
            self.assertEqual(
                get_variation_rule_preset_for_profile(preset_id).target_profile,
                preset_id,
            )

    def test_unsupported_profile_falls_back_to_unknown_preset(self) -> None:
        preset = get_variation_rule_preset_for_profile("unsupported_profile")

        self.assertEqual(preset.id, "unknown")

    def test_unknown_preset_id_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_variation_rule_preset("unsupported_preset")

    def test_transform_ranges_are_ordered(self) -> None:
        for preset in VARIATION_RULE_PRESETS:
            for field in dataclasses.fields(preset.transform_ranges):
                value_range = getattr(preset.transform_ranges, field.name)
                self.assertLessEqual(
                    value_range.min_value,
                    value_range.max_value,
                    f"{preset.id}.{field.name}",
                )

    def test_tonal_presets_use_major_thirds_around_source(self) -> None:
        for preset_id in ["tonal_percussive", "sustained_tonal"]:
            pitch_mapping = get_variation_rule_preset(preset_id).pitch_mapping

            self.assertTrue(pitch_mapping.enabled)
            self.assertEqual(pitch_mapping.strategy, MAJOR_THIRDS_AROUND_SOURCE)
            self.assertEqual(pitch_mapping.interval_semitones, 4)
            self.assertEqual(pitch_mapping.octave_radius, 2)
            self.assertTrue(pitch_mapping.include_source_note)

    def test_non_tonal_and_unknown_presets_use_source_only(self) -> None:
        for preset_id in ["percussive", "sfx_texture", "unknown"]:
            pitch_mapping = get_variation_rule_preset(preset_id).pitch_mapping

            self.assertFalse(pitch_mapping.enabled)
            self.assertEqual(pitch_mapping.strategy, SOURCE_ONLY)


if __name__ == "__main__":
    unittest.main()

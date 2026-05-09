import unittest

from variation_engine.analysis.categories import (
    AUTO,
    DEFAULT_PROFILE_BY_CATEGORY_ID,
    INSTRUMENT_CATEGORIES,
    NON_HORNBOSTEL_SACHS,
    get_instrument_category,
)


class InstrumentCategorySchemaTest(unittest.TestCase):
    def test_defines_expected_category_ids_in_stable_order(self) -> None:
        self.assertEqual(
            [category.id for category in INSTRUMENT_CATEGORIES],
            [
                "piano_keys",
                "plucked_string",
                "bowed_string",
                "guitar_bass",
                "drum_percussion",
                "synth_lead",
                "synth_pad",
                "vocal_voice",
                "fx_foley_texture",
                "unknown_auto",
            ],
        )

    def test_maps_categories_to_internal_default_profiles(self) -> None:
        self.assertEqual(
            DEFAULT_PROFILE_BY_CATEGORY_ID,
            {
                "piano_keys": "tonal_percussive",
                "plucked_string": "tonal_percussive",
                "bowed_string": "sustained_tonal",
                "guitar_bass": "tonal_percussive",
                "drum_percussion": "percussive",
                "synth_lead": "sustained_tonal",
                "synth_pad": "sustained_tonal",
                "vocal_voice": "sustained_tonal",
                "fx_foley_texture": "sfx_texture",
                "unknown_auto": "unknown",
            },
        )

    def test_fx_foley_texture_is_first_class_non_hornbostel_sachs_category(self) -> None:
        category = get_instrument_category("fx_foley_texture")

        self.assertEqual(category.label, "FX / Foley / Texture")
        self.assertEqual(category.domain, NON_HORNBOSTEL_SACHS)
        self.assertEqual(category.default_profile, "sfx_texture")
        self.assertEqual(category.hornbostel_sachs_hint, ())
        self.assertTrue(category.allows_pitch_variation)
        self.assertTrue(category.allows_attack_variation)
        self.assertTrue(category.allows_timbre_variation)
        self.assertTrue(category.allows_space_variation)

    def test_unknown_auto_is_explicit_category(self) -> None:
        category = get_instrument_category("unknown_auto")

        self.assertEqual(category.label, "Unknown / Auto")
        self.assertEqual(category.domain, AUTO)
        self.assertEqual(category.default_profile, "unknown")
        self.assertEqual(category.hornbostel_sachs_hint, ())

    def test_unknown_category_id_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_instrument_category("hornbostel_sachs_auto")


if __name__ == "__main__":
    unittest.main()

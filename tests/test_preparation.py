# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from native_profile import (BASE_MODEL, ENVELOPE_MODEL, FACTORY_SHA256, encode_profile,
                            json_bytes, read_json, sha256)
from check_firmware import inspect_firmware
from import_darkslide import fitted_entry, prepare
from verify_assets import verify_assets


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.project = self.folder / "darkslide-project"
        (self.project / "luts").mkdir(parents=True)
        cube = b"LUT_3D_SIZE 2\n" + b"0 0 0\n" * 8
        self.ident = "user_lut_" + sha256(cube)[:12]
        (self.project / "luts" / (self.ident + ".cube")).write_bytes(cube)
        self.profile = read_json(ROOT / "assets/presets/ektar100/profile.json")
        self.profile["id"] = self.ident
        self.profile["provenance"] = dict(
            kind="user_lut", source_sha256=sha256(cube), official_sha256=FACTORY_SHA256,
            fitter="darkslide-film-fit-v2", base_model_id=BASE_MODEL,
            target_input_encoding="srgb", target_ev=0, mid_index=7.8,
            base_values_sha256="1" * 64)
        self.entry = dict(name="My film", sha256=sha256(cube), profile=self.profile,
                          fit=dict(fitter="darkslide-film-fit-v2", base_model_id=BASE_MODEL,
                                   layout="four_curve_v1", envelope=dict(
                                       checked=True, model_id=ENVELOPE_MODEL, violations=[])))
        self.save()

    def save(self):
        (self.project / "project.json").write_bytes(json_bytes(dict(input_sha256=FACTORY_SHA256)))
        (self.project / "film_luts.json").write_bytes(json_bytes({self.ident: self.entry}))

    def test_all_curated_assets_encode_exactly(self):
        self.assertEqual(verify_assets()["films"], 51)

    def test_fitted_project_native_data(self):
        entry, profile, files = fitted_entry(self.project, self.ident)
        self.assertEqual(profile["id"], self.ident)
        self.assertEqual([len(files[n]) for n in (
            "M1_Q13_s16.bin", "RGB_GAMMA_u16.bin", "M2_NATIVE_CSP_Q13_s32.bin")], [18, 1536, 36])

    def test_cube_only_rejected(self):
        self.entry.pop("profile")
        self.save()
        with self.assertRaisesRegex(ValueError, "no fitted"):
            fitted_entry(self.project, self.ident)

    def test_preview_cube_cannot_replace_source(self):
        (self.project / "luts" / (self.ident + ".cube")).write_bytes(b"TITLE camera preview\n")
        with self.assertRaises(ValueError):
            fitted_entry(self.project, self.ident)

    def test_wrong_model_rejected(self):
        self.profile["model"] = "GR IIIx"
        self.save()
        with self.assertRaisesRegex(ValueError, "Only standard"):
            fitted_entry(self.project, self.ident)

    def test_other_base_model_rejected(self):
        self.profile["provenance"]["base_model_id"] = "gr3-210-python-standard-p64-zero-v1"
        self.save()
        with self.assertRaisesRegex(ValueError, "base model"):
            fitted_entry(self.project, self.ident)

    def test_wrong_original_hash_rejected(self):
        self.profile["provenance"]["official_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "provenance"):
            fitted_entry(self.project, self.ident)

    def test_missing_envelope_rejected(self):
        self.entry["fit"].pop("envelope")
        self.save()
        with self.assertRaisesRegex(ValueError, "envelope"):
            fitted_entry(self.project, self.ident)

    def test_bad_source_hash_rejected(self):
        self.entry["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "SHA"):
            fitted_entry(self.project, self.ident)

    def test_bool_in_integer_matrix_rejected(self):
        self.profile["look_matrix_q13"][0][0] = True
        with self.assertRaises(ValueError):
            encode_profile(self.profile)

    def test_nonfinite_and_duplicate_json_rejected(self):
        for content in ('{"a": NaN}', '{"a": 1e999}', '{"a": 1, "a": 2}'):
            file = self.folder / "bad.json"
            file.write_text(content)
            with self.assertRaises(ValueError):
                read_json(file)

    def test_invalid_firmware_rejected(self):
        file = self.folder / "fwdc239b.bin"
        file.write_bytes(b"modified or wrong model")
        with self.assertRaisesRegex(ValueError, "exact official"):
            inspect_firmware(file)

    def test_native_overflow_rejected(self):
        self.profile["post_matrix_q512"] = [[32767, -32255, 0]] * 3
        with self.assertRaises(ValueError):
            encode_profile(self.profile)

    @patch("import_darkslide.inspect_firmware", return_value={"test_fixture": True})
    def test_append_retry_and_private_output(self, unused):
        before = {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        first = self.folder / "first"
        receipt = prepare(self.project, [self.ident], self.folder / "official.bin", first)
        self.assertEqual(receipt["new_films"], 1)
        self.assertFalse(receipt["firmware_generated"])
        manifest = read_json(first / "library.json")
        self.assertEqual(manifest["next_uid"], 86)
        self.assertEqual(manifest["films"][-1]["uid"], 85)
        second = self.folder / "second"
        receipt = prepare(self.project, [self.ident], self.folder / "official.bin", second, first)
        self.assertEqual(receipt["new_films"], 0)
        self.assertEqual(read_json(second / "library.json")["next_uid"], 86)
        with self.assertRaisesRegex(ValueError, "fresh"):
            prepare(self.project, [self.ident], self.folder / "official.bin", first)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()})

    @patch("import_darkslide.inspect_firmware", return_value={"test_fixture": True})
    def test_display_name_override(self, unused):
        self.entry["name"] = "中文胶片"
        self.save()
        output = self.folder / "named"
        prepare(self.project, [self.ident], self.folder / "official.bin", output, name="My custom film")
        self.assertEqual(read_json(output / "library.json")["films"][-1]["name"], "My custom film")

    @patch("import_darkslide.inspect_firmware", return_value={"test_fixture": True})
    def test_all_input_checks_precede_publication(self, unused):
        self.entry["fit"]["envelope"]["checked"] = False
        self.save()
        output = self.folder / "invalid"
        with self.assertRaises(ValueError):
            prepare(self.project, [self.ident], self.folder / "official.bin", output)
        self.assertFalse(output.exists())

    def test_user_data_cannot_enter_skill_repository(self):
        with self.assertRaisesRegex(ValueError, "outside the skill"):
            prepare(self.project, [self.ident], self.folder / "official.bin", ROOT / "private-test")

    @unittest.skipUnless(os.environ.get("GRSLOT_OFFICIAL_FIRMWARE"), "Set official input for container integration")
    def test_real_official_container(self):
        receipt = inspect_firmware(Path(os.environ["GRSLOT_OFFICIAL_FIRMWARE"]))
        self.assertEqual(receipt["status"], "PASS_OFFICIAL_INPUT_ONLY")


if __name__ == "__main__":
    unittest.main()

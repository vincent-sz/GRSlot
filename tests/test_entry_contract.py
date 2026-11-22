# SPDX-License-Identifier: GPL-2.0-only
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EntryContractTests(unittest.TestCase):
    def test_method_scope_precedes_execution(self):
        text = (ROOT / "SKILL.md").read_text()
        start = text.index("## 先读能力状态")
        workflow = text.index("## 按任务读取和执行")
        self.assertLess(start, workflow)
        self.assertIn("offline_build_checks", text[start:workflow])
        self.assertIn("firmware_container_output", text[start:workflow])

    def test_draw_checks_active_panel_before_painting(self):
        text = (ROOT / "source/filminfo/menu.c").read_text()
        body = text.split("void grs_draw(struct canvas*c){", 1)[1].split('#include "native_frame.inc"', 1)[0]
        panel_guard = body.index("0x540c5a58u;if(!active())return;")
        self.assertLess(panel_guard, body.index("rect(c,0,0"))
        self.assertLess(panel_guard, body.index("nav(s)"))

    def test_families_are_in_the_actual_grid_draw_branch(self):
        text = (ROOT / "source/filminfo/menu.c").read_text()
        body = text.split("void grs_draw(struct canvas*c){", 1)[1]
        self.assertIn("if(n->view==SLOTS||n->view==GRID||n->view==FAMILIES){", body)
        self.assertIn("family_names[family]", body)

    def test_capabilities_match_build_and_card_entries(self):
        self.assertFalse((ROOT / "scripts/firmware.py").exists())
        self.assertFalse((ROOT / "scripts/sd_package.py").exists())
        capabilities = json.loads((ROOT / "assets/capabilities.json").read_text())
        builder = (ROOT / "studio-lite/build_firmware.py").is_file()
        self.assertEqual(capabilities["offline_build_checks"], builder)
        self.assertEqual(capabilities["firmware_candidate_output"], builder)
        self.assertFalse(capabilities["firmware_container_output"])
        self.assertFalse(capabilities["sd_deployment"])

    def test_distribution_and_private_variants_are_separate(self):
        library = json.loads((ROOT / "assets/library.json").read_text())
        self.assertEqual(len(library["films"]), 59)
        self.assertEqual(library["defaults"], [39, 40, 88, 41, 5, 86])
        self.assertTrue(all(film["license"] in {"CC-BY-SA-4.0", "MIT",
                                                "MAINTAINER_APPROVED_FOR_PUBLIC_DISTRIBUTION"} for film in library["films"]))
        self.assertFalse((ROOT / "assets/private").exists())


if __name__ == "__main__":
    unittest.main()

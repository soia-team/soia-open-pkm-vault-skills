"""Offline contract tests for generic X profile research and image routing."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "soia-pkm-clip-x-profile" / "scripts" / "profile_x.py"
SPEC = importlib.util.spec_from_file_location("profile_x", SCRIPT)
assert SPEC and SPEC.loader
profile_x = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile_x)


def fixture_status(status_id: str, created_at: str, title: str, alt: str = "") -> dict:
    photo = {"id": f"media-{status_id}", "type": "photo", "url": f"https://pbs.twimg.com/{status_id}.jpg", "altText": alt}
    return {
        "type": "status",
        "id": status_id,
        "url": f"https://x.com/example/status/{status_id}",
        "text": title,
        "created_at": created_at,
        "created_timestamp": None,
        "author": {"screen_name": "example", "name": "Example"},
        "media": {"photos": [photo]},
    }


class ProfileXTests(unittest.TestCase):
    def test_parse_handle_and_cst_month_filter(self) -> None:
        self.assertEqual(profile_x.parse_handle("https://x.com/xiaoxiaodong01"), "xiaoxiaodong01")
        self.assertEqual(profile_x.parse_handle("@example"), "example")
        july = profile_x.normalize_status(
            fixture_status("1", "Thu Jul 30 03:00:00 +0000 2026", "GPT2 x 早安 x 字体蒙版")
        )
        august = profile_x.normalize_status(
            fixture_status("2", "Sat Aug 01 03:00:00 +0000 2026", "GPT2 x PPT")
        )
        selected = profile_x.filter_month([july, august], "2026-07")
        self.assertEqual([row["id"] for row in selected], ["1"])

    def test_alt_text_is_prompt_evidence_and_gpt2_is_not_a_family(self) -> None:
        row = profile_x.normalize_status(
            fixture_status(
                "1",
                "Thu Jul 30 03:00:00 +0000 2026",
                "GPT2 x 早安 x 字体蒙版 x 美学提示词",
                "主题：10 个城市；巨型字形蒙版；比例 16:9",
            )
        )
        classification = profile_x.classify(row)
        compiled = profile_x.compile_prompt(row, classification)
        self.assertEqual(classification["primary_category"], "morning_city")
        self.assertTrue(classification["is_gpt2"])
        self.assertEqual(classification["evidence_source"], "image_alt_text")
        self.assertEqual(compiled["composition_axes"]["family"], "morning_city")
        self.assertEqual(compiled["composition_axes"]["model_adapter"], "external_gpt_image_label")
        self.assertNotEqual(compiled["composition_axes"]["family"], "GPT2")
        self.assertEqual(
            set(compiled["prompt_blocks"]),
            {
                "source_grounding",
                "primary_task",
                "composition_and_layout",
                "visual_style_and_materials",
                "exact_text",
                "aspect_and_output",
                "constraints_and_avoid",
            },
        )

    def test_query_and_period_filters_are_generic(self) -> None:
        rows = [
            profile_x.normalize_status(fixture_status("1", "Thu Jul 30 03:00:00 +0000 2026", "GPT2 x 早安", "城市提示词")),
            profile_x.normalize_status(fixture_status("2", "Sat Aug 01 03:00:00 +0000 2026", "GPT2 x PPT", "课程页面")),
            profile_x.normalize_status(fixture_status("3", "Wed Jul 29 03:00:00 +0000 2026", "酒店活动总结", "餐饮现场")),
        ]
        recent = profile_x.filter_records(rows, since="2026-07-29", until="2026-07-31", queries=["提示词"], has_media=True)
        self.assertEqual([row["id"] for row in recent], ["1"])
        all_terms = profile_x.filter_records(rows, queries=["酒店", "餐饮"], query_mode="all")
        self.assertEqual([row["id"] for row in all_terms], ["3"])

    def test_summary_mode_does_not_compile_image_prompts(self) -> None:
        fixture = {"profile": {"name": "Example", "id": "profile-1"}, "results": [
            fixture_status("1", "Thu Jul 30 03:00:00 +0000 2026", "账号周报", "本周完成了三项工作"),
            fixture_status("2", "Sat Aug 01 03:00:00 +0000 2026", "GPT2 x PPT", "图片提示词"),
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.json"
            output = tmp_path / "run"
            source.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            profile_x.main(["https://x.com/example", "--limit", "2", "--query", "周报", "--source-json", str(source), "--output", str(output)])
            self.assertTrue((output / "summary.md").is_file())
            self.assertTrue((output / "filtered.json").is_file())
            self.assertFalse((output / "image-prompts.yml").exists())

    def test_fixture_cli_writes_auditable_bundle(self) -> None:
        fixture = {
            "profile": {"name": "Example", "id": "profile-1"},
            "results": [
                fixture_status("1", "Thu Jul 30 03:00:00 +0000 2026", "GPT2 x 早安 x 字体蒙版", "主题：城市和日期"),
                fixture_status("2", "Sat Aug 01 03:00:00 +0000 2026", "GPT2 x PPT", "主题：报告型页面"),
                fixture_status("3", "Wed Jul 29 03:00:00 +0000 2026", "酒店 x 海报", "主题：酒店大堂"),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.json"
            output = tmp_path / "run"
            source.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            exit_code = profile_x.main(
                [
                    "https://x.com/example",
                    "--limit",
                    "3",
                    "--month",
                    "2026-07",
                    "--only-gpt2",
                    "--output-mode",
                    "image-prompts",
                    "--source-json",
                    str(source),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "manifest.yml").is_file())
            self.assertTrue((output / "classification.yml").is_file())
            self.assertTrue((output / "image-prompts.yml").is_file())
            prompts = list((output / "prompts").glob("*.md"))
            self.assertEqual(len(prompts), 1)
            prompt_index = json.loads("\n".join((output / "image-prompts.yml").read_text(encoding="utf-8").splitlines()[1:]))
            self.assertEqual(prompt_index["selection"]["selected"], 1)
            self.assertEqual(len(prompt_index["items"]), 1)


if __name__ == "__main__":
    unittest.main()

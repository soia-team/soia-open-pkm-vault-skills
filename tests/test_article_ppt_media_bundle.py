import argparse
import binascii
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "soia-pkm-transform-article-ppt" / "scripts" / "media_bundle.py"
SPEC = importlib.util.spec_from_file_location("article_ppt_media_bundle", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


EDITABLE_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
</p:sld>
"""

IMAGE_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:pic/></p:spTree></p:cSld>
</p:sld>
"""


def write_fake_pptx(path: Path, slides: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for index, slide in enumerate(slides, 1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide)


def write_png_header(path: Path, width: int = 1080, height: int = 720) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    row = b"\x00" + (b"\x00" * ((width + 7) // 8))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def write_truncated_png_header(path: Path, width: int = 1080, height: int = 720) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height))


def write_invalid_idat_png(path: Path, width: int = 1080, height: int = 720) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", b"not-a-zlib-stream")
        + chunk(b"IEND", b"")
    )


class ArticlePptMediaBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.article = self.root / "example.md"
        self.article.write_text(
            """---
title: 示例文章
author: Example Author
url: https://example.com/article
published_at: 2026-07-22 09:37
---
# 示例文章
## 模型基础
**1. Token（词元）** 模型的工作单位。
## 工具扩展
**2. Agent（智能体）** 模型、规划和工具的组合。
""",
            encoding="utf-8",
        )
        self.out_dir = self.root / "out"

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **overrides):
        values = {
            "article": str(self.article),
            "out_dir": str(self.out_dir),
            "provider": "hybrid",
            "audience": "初学者",
            "style": "course_module",
            "slide_count": "2",
            "image_count": 1,
            "infographic": True,
            "main_verdict": "术语要放回系统链路理解",
            "purpose": "教学",
            "delivery_context": "live",
            "language": "zh-Hans",
            "review_mode": "standard",
        }
        values.update(overrides)
        manifest = MODULE.build_manifest(argparse.Namespace(**values))
        MODULE.write_json(self.out_dir / "media-manifest.json", manifest)
        return manifest

    def materialize_quality_contracts(self, *, cjk_passed: bool = True, empty_claims: bool = False):
        payloads = {
            "planning/content-plan.json": {
                "schema_version": 1,
                "status": "approved",
                "main_verdict": "术语要放回系统链路理解",
                "claim_ledger": []
                if empty_claims
                else [
                    {
                        "claim": "Token 是模型的工作单位",
                        "source_anchor": "## 模型基础",
                        "status": "source-confirmed",
                    }
                ],
                "narrative_arc": ["从概念到系统"],
                "slide_plan": [
                    {
                        "slide": 1,
                        "title": "先理解工作单位",
                        "page_job": "解释 Token",
                        "source_anchor": "## 模型基础",
                    },
                    {
                        "slide": 2,
                        "title": "再理解工具扩展",
                        "page_job": "解释 Agent",
                        "source_anchor": "## 工具扩展",
                    },
                ],
                "open_questions": [],
            },
            "planning/design-plan.json": {
                "schema_version": 1,
                "status": "approved",
                "design_language": "结构蓝图",
                "boldness": "balanced+",
                "signature_move": "把系统边界画成一扇门",
                "signature_slides": [1],
                "semantic_colors": {"主线": "blue", "风险": "orange"},
                "slide_shapes": ["cover", "flow"],
                "rhythm_map": ["hero", "diagram"],
            },
            "planning/contract-card.json": {
                "schema_version": 1,
                "status": "approved",
                "source": str(self.article),
                "audience": "初学者",
                "purpose": "教学",
                "delivery_context": "live",
                "language": "zh-Hans",
                "editability": "editable_pptx",
                "review_mode": "standard",
                "output_scope": ["editable_pptx", "notebooklm_pptx", "infographic", "visual_assets"],
            },
            "qa/signature-proof.json": {
                "schema_version": 1,
                "status": "passed",
                "signature_move": "把系统边界画成一扇门",
                "slides": [1],
                "preview_paths": ["previews/editable/slide-1.png"],
                "reason": "",
            },
            "qa/critic-content.json": {
                "schema_version": 1,
                "status": "completed",
                "lens": "content",
                "reviewer": "content-critic",
                "independent_of_builder": True,
                "round": 1,
                "verdict": "consent",
                "blockers": [],
                "majors": [],
                "advisories": [],
            },
            "qa/critic-design.json": {
                "schema_version": 1,
                "status": "completed",
                "lens": "design",
                "reviewer": "design-critic",
                "independent_of_builder": True,
                "round": 1,
                "verdict": "consent",
                "blockers": [],
                "majors": [],
                "advisories": ["可继续加强结尾页的方向性"],
            },
            "qa/host-validation.json": {
                "schema_version": 1,
                "status": "passed",
                "host": "microsoft_powerpoint",
                "preview_dir": "previews/editable",
                "rendered_slide_count": 2,
                "cjk_checked": True,
                "cjk_passed": cjk_passed,
                "notes": "中文标题和正文显示正常",
            },
        }
        for relative_path, payload in payloads.items():
            MODULE.write_json(self.out_dir / relative_path, payload)

    def materialize_valid_bundle(self, placeholder: bool = False):
        manifest = self.plan()
        stem = self.article.stem
        local_text = "[ARTIFACT_ID_PLACEHOLDER]" if placeholder else "可编辑标题"
        write_fake_pptx(
            self.out_dir / f"{stem}-editable.pptx",
            [EDITABLE_SLIDE.format(text=local_text), EDITABLE_SLIDE.format(text="来源")],
        )
        write_fake_pptx(
            self.out_dir / f"{stem}-notebooklm.pptx",
            [IMAGE_SLIDE, IMAGE_SLIDE],
        )
        for preview_dir in ("previews/editable", "previews/notebooklm"):
            write_png_header(self.out_dir / preview_dir / "slide-1.png")
            write_png_header(self.out_dir / preview_dir / "slide-2.png")
        write_png_header(self.out_dir / "assets/imagegen/image-01.png", 1024, 1024)
        write_png_header(self.out_dir / f"{stem}-infographic.png", 1080, 1600)
        for entry in manifest["expected"]["prompts"]:
            path = self.out_dir / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("prompt\n", encoding="utf-8")
        self.materialize_quality_contracts()
        return manifest

    def test_plan_extracts_source_and_hybrid_contract(self):
        manifest = self.plan()
        self.assertEqual(manifest["source"]["title"], "示例文章")
        self.assertEqual(manifest["source"]["published_at"], "2026-07-22 09:37")
        self.assertIn("模型基础", manifest["source"]["sections"])
        self.assertIn("Token", manifest["source"]["concepts"])
        self.assertTrue(manifest["expected"]["editable_pptx"]["required"])
        self.assertTrue(manifest["expected"]["notebooklm_pptx"]["required"])
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["request"]["review_mode"], "standard")
        self.assertTrue(manifest["source"]["contains_cjk"])
        self.assertNotIn("created_by", json.dumps(manifest, ensure_ascii=False))

    def test_plan_templates_are_created_without_overwriting_existing_files(self):
        manifest = self.plan()
        MODULE.write_planning_templates(self.out_dir, manifest)
        content_path = self.out_dir / "planning/content-plan.json"
        payload = json.loads(content_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "draft")
        payload["status"] = "approved"
        MODULE.write_json(content_path, payload)
        MODULE.write_planning_templates(self.out_dir, manifest)
        self.assertEqual(json.loads(content_path.read_text(encoding="utf-8"))["status"], "approved")

    def test_plan_rejects_blank_main_verdict(self):
        with self.assertRaisesRegex(ValueError, "main_verdict must be non-empty"):
            self.plan(main_verdict="   ")

    def test_strict_validation_passes_complete_hybrid_bundle(self):
        self.materialize_valid_bundle()
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(any(item["code"] == "notebooklm_deck_is_flattened" for item in report["warnings"]))
        self.assertTrue(report["manual_gates"]["dual_lens_consented"])
        self.assertTrue(report["manual_gates"]["host_validated"])

    def test_placeholder_in_editable_pptx_fails(self):
        self.materialize_valid_bundle(placeholder=True)
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "runtime_metadata_editable_pptx" for item in report["errors"]))

    def test_empty_claim_ledger_fails(self):
        self.materialize_valid_bundle()
        self.materialize_quality_contracts(empty_claims=True)
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "claim_ledger_empty" for item in report["errors"]))

    def test_failed_cjk_host_check_blocks_delivery(self):
        self.materialize_valid_bundle()
        self.materialize_quality_contracts(cjk_passed=False)
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "host_validation_cjk_failed" for item in report["errors"]))

    def test_missing_signature_preview_blocks_delivery(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/signature-proof.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["preview_paths"] = ["previews/editable/not-created.png"]
        MODULE.write_json(path, payload)
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "signature_proof_preview_missing" for item in report["errors"]))

    def test_self_reviewed_critic_blocks_delivery(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/critic-content.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["independent_of_builder"] = False
        MODULE.write_json(path, payload)
        args = argparse.Namespace(
            manifest=str(self.out_dir / "media-manifest.json"),
            visual_reviewed=True,
            source_facts_reviewed=True,
            strict=True,
        )
        report, exit_code = MODULE.validate_manifest(args)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "critic_content_not_independent" for item in report["errors"]))

    def validate(self):
        return MODULE.validate_manifest(
            argparse.Namespace(
                manifest=str(self.out_dir / "media-manifest.json"),
                visual_reviewed=True,
                source_facts_reviewed=True,
                strict=True,
            )
        )

    def test_missing_planning_or_qa_contract_cannot_bypass_strict_gate(self):
        for field in ("planning", "qa"):
            with self.subTest(field=field):
                self.materialize_valid_bundle()
                manifest_path = self.out_dir / "media-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                del manifest["expected"][field]
                MODULE.write_json(manifest_path, manifest)
                report, exit_code = self.validate()
                self.assertEqual(exit_code, 1)
                self.assertTrue(any(item["code"] == f"manifest_{field}_missing" for item in report["errors"]))

    def test_missing_required_contract_role_cannot_bypass_strict_gate(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expected"]["qa"] = [
            item for item in manifest["expected"]["qa"] if item["role"] != "design_critic"
        ]
        MODULE.write_json(manifest_path, manifest)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(any("design_critic" in item["message"] for item in report["errors"]))

    def test_contract_card_drift_blocks_delivery(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "planning/contract-card.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["audience"] = "管理层"
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "contract_card_audience_mismatch" for item in report["errors"]))

    def test_signature_skip_requires_tiny_or_conservative_deck(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["request"]["slide_count"] = 10
        manifest["expected"]["editable_pptx"]["min_slides"] = 2
        manifest["expected"]["notebooklm_pptx"]["min_slides"] = 2
        MODULE.write_json(manifest_path, manifest)
        path = self.out_dir / "qa/signature-proof.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update({"status": "skipped", "reason": "想省时间", "slides": [], "preview_paths": []})
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "signature_proof_skip_not_allowed" for item in report["errors"]))

    def test_host_requires_supported_renderer_and_real_preview_evidence(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/host-validation.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["host"] = "browser_self_report"
        payload["preview_dir"] = "previews/not-created"
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("host_validation_invalid_host", codes)
        self.assertIn("host_validation_preview_missing", codes)

    def test_host_preview_count_must_match_actual_deck(self):
        self.materialize_valid_bundle()
        (self.out_dir / "previews/editable/slide-2.png").unlink()
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "host_validation_preview_count" for item in report["errors"]))

    def test_target_language_requires_cjk_check_even_for_english_source(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source"]["contains_cjk"] = False
        MODULE.write_json(manifest_path, manifest)
        self.materialize_quality_contracts(cjk_passed=False)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(item["code"] == "host_validation_cjk_failed" for item in report["errors"]))

    def test_string_false_cannot_satisfy_boolean_quality_gates(self):
        self.materialize_valid_bundle()
        critic_path = self.out_dir / "qa/critic-content.json"
        critic = json.loads(critic_path.read_text(encoding="utf-8"))
        critic["independent_of_builder"] = "false"
        MODULE.write_json(critic_path, critic)
        host_path = self.out_dir / "qa/host-validation.json"
        host = json.loads(host_path.read_text(encoding="utf-8"))
        host["cjk_checked"] = "false"
        host["cjk_passed"] = "false"
        MODULE.write_json(host_path, host)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("critic_content_not_independent", codes)
        self.assertIn("host_validation_cjk_failed", codes)

    def test_empty_or_undersized_preview_png_blocks_delivery(self):
        self.materialize_valid_bundle()
        (self.out_dir / "previews/editable/slide-1.png").write_bytes(b"")
        write_png_header(self.out_dir / "previews/notebooklm/slide-1.png", 1, 1)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("invalid_preview_editable_pptx", codes)
        self.assertIn("invalid_preview_notebooklm_pptx", codes)
        self.assertIn("host_validation_preview_invalid", codes)
        self.assertIn("signature_proof_preview_invalid", codes)

    def test_truncated_header_only_png_blocks_delivery(self):
        self.materialize_valid_bundle()
        write_truncated_png_header(self.out_dir / "previews/editable/slide-1.png")
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("invalid_preview_editable_pptx", codes)
        self.assertIn("host_validation_preview_invalid", codes)
        self.assertIn("signature_proof_preview_invalid", codes)

    def test_crc_correct_but_undecodable_png_blocks_delivery(self):
        self.materialize_valid_bundle()
        write_invalid_idat_png(self.out_dir / "previews/editable/slide-1.png")
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("invalid_preview_editable_pptx", codes)
        self.assertIn("host_validation_preview_invalid", codes)
        self.assertIn("signature_proof_preview_invalid", codes)

    def test_signature_proof_must_match_move_and_slide_preview(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/signature-proof.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["signature_move"] = "无关签名动作"
        payload["preview_paths"] = ["previews/editable/slide-2.png"]
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("signature_proof_move_mismatch", codes)
        self.assertIn("signature_proof_slide_preview_mismatch", codes)

    def test_signature_proof_must_use_primary_deck_preview_directory(self):
        self.materialize_valid_bundle()
        unrelated = self.out_dir / "assets/imagegen/slide-1.png"
        write_png_header(unrelated)
        path = self.out_dir / "qa/signature-proof.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["preview_paths"] = ["assets/imagegen/slide-1.png"]
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(item["code"] == "signature_proof_preview_wrong_origin" for item in report["errors"])
        )

    def test_signature_proof_rejects_duplicate_slide_evidence(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/signature-proof.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["slides"] = [1, 1]
        payload["preview_paths"] = [
            "previews/editable/slide-1.png",
            "previews/editable/slide-1.png",
        ]
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(item["code"] == "signature_proof_slide_preview_mismatch" for item in report["errors"])
        )

    def test_preview_and_asset_directories_cannot_escape_bundle(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expected"]["editable_pptx"]["preview_dir"] = "../outside-previews"
        manifest["expected"]["visual_assets"]["directory"] = "../outside-assets"
        MODULE.write_json(manifest_path, manifest)
        write_png_header(self.root / "outside-previews/slide-1.png")
        write_png_header(self.root / "outside-previews/slide-2.png")
        write_png_header(self.root / "outside-assets/image-01.png", 1024, 1024)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("preview_dir_escape_editable_pptx", codes)
        self.assertIn("visual_assets_directory_escape", codes)

    def test_required_decks_cannot_share_preview_directory(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expected"]["notebooklm_pptx"]["preview_dir"] = "previews/editable"
        MODULE.write_json(manifest_path, manifest)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(item["code"] == "manifest_preview_dir_conflict" for item in report["errors"])
        )

    def test_host_validation_must_bind_primary_deck_preview(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/host-validation.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["preview_dir"] = "previews/notebooklm"
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(
                item["code"] == "host_validation_preview_origin_mismatch"
                for item in report["errors"]
            )
        )

    def test_content_plan_verdict_must_match_manifest_verdict(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["request"]["main_verdict"] = "重跑后改变的判断"
        MODULE.write_json(manifest_path, manifest)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(item["code"] == "content_plan_verdict_mismatch" for item in report["errors"])
        )

    def test_schema_v2_manifest_requires_nonempty_main_verdict(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["request"]["main_verdict"] = ""
        MODULE.write_json(manifest_path, manifest)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("manifest_main_verdict_missing", codes)
        self.assertIn("content_plan_verdict_mismatch", codes)

    def test_v1_manifest_is_readable_but_cannot_pass_strict_delivery(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = 1
        manifest["expected"].pop("planning")
        manifest["expected"].pop("qa")
        for field in ("purpose", "delivery_context", "language", "review_mode"):
            manifest["request"].pop(field)
        MODULE.write_json(manifest_path, manifest)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(
            any(
                item["code"] == "manifest_schema_legacy_strict_unsupported"
                for item in report["errors"]
            )
        )
        self.assertFalse(any(item["code"] == "manifest_schema_invalid" for item in report["errors"]))
        report, exit_code = MODULE.validate_manifest(
            argparse.Namespace(
                manifest=str(manifest_path),
                visual_reviewed=True,
                source_facts_reviewed=True,
                strict=False,
            )
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "legacy")

    def test_libreoffice_validation_must_record_host_limit(self):
        self.materialize_valid_bundle()
        path = self.out_dir / "qa/host-validation.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["host"] = "libreoffice"
        payload["notes"] = ""
        MODULE.write_json(path, payload)
        report, exit_code = self.validate()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any(
                item["code"] == "host_validation_libreoffice_limit_missing"
                for item in report["errors"]
            )
        )

    def test_config_uses_validator_host_enum(self):
        config = (
            ROOT / "skills" / "soia-pkm-transform-article-ppt" / "config.example.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("apple_keynote", config)
        self.assertNotIn("| keynote |", config)


if __name__ == "__main__":
    unittest.main()

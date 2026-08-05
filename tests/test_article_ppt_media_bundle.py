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
from unittest import mock


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


TABLE_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:rPr typeface="Aptos"/><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>
    <p:graphicFrame>
      <p:xfrm><a:off x="100000" y="100000"/><a:ext cx="6000000" cy="3000000"/></p:xfrm>
      <a:graphic><a:graphicData><a:tbl><a:tr><a:tc/></a:tr></a:tbl></a:graphicData></a:graphic>
    </p:graphicFrame>
  </p:spTree></p:cSld>
</p:sld>
"""


CHART_TABLE_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:rPr typeface="Aptos"/><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>
    <p:graphicFrame>
      <p:xfrm><a:off x="100000" y="100000"/><a:ext cx="5000000" cy="2400000"/></p:xfrm>
      <a:graphic><a:graphicData><c:chart r:id="rId1"/></a:graphicData></a:graphic>
    </p:graphicFrame>
    <p:graphicFrame>
      <p:xfrm><a:off x="100000" y="2700000"/><a:ext cx="6000000" cy="3000000"/></p:xfrm>
      <a:graphic><a:graphicData><a:tbl><a:tr><a:tc/></a:tr></a:tbl></a:graphicData></a:graphic>
    </p:graphicFrame>
  </p:spTree></p:cSld>
</p:sld>
"""


OVERFLOW_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:graphicFrame>
      <p:xfrm><a:off x="12000000" y="100000"/><a:ext cx="1000000" cy="1000000"/></p:xfrm>
      <a:graphic><a:graphicData><a:tbl><a:tr><a:tc/></a:tr></a:tbl></a:graphicData></a:graphic>
    </p:graphicFrame>
  </p:spTree></p:cSld>
</p:sld>
"""


PRESENTATION_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>
"""

MASTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree/></p:cSld>
</p:sldMaster>
"""

LAYOUT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree/></p:cSld>
</p:sldLayout>
"""


def write_fake_pptx(path: Path, slides: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        overrides = "".join(
            f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            for index in range(1, len(slides) + 1)
        )
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
            '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
            + overrides
            + "</Types>",
        )
        archive.writestr("ppt/presentation.xml", PRESENTATION_XML)
        archive.writestr("ppt/slideMasters/slideMaster1.xml", MASTER_XML)
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT_XML)
        chart_index = 0
        for index, slide in enumerate(slides, 1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide)
            relationship_entries = []
            for relationship_index in range(1, slide.count("<c:chart") + 1):
                chart_index += 1
                archive.writestr(
                    f"ppt/charts/chart{chart_index}.xml",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart/></c:chartSpace>',
                )
                relationship_entries.append(
                    f'<Relationship Id="rId{relationship_index}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
                    f'Target="../charts/chart{chart_index}.xml"/>'
                )
            if relationship_entries:
                archive.writestr(
                    f"ppt/slides/_rels/slide{index}.xml.rels",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + "".join(relationship_entries)
                    + "</Relationships>",
                )


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
        MODULE.write_json(Path(values["out_dir"]) / "media-manifest.json", manifest)
        return manifest

    def materialize_quality_contracts(
        self,
        *,
        cjk_passed: bool = True,
        empty_claims: bool = False,
        expected_editable_charts: int = 0,
        expected_native_tables: int = 0,
        table_pagination_required: bool = False,
        table_page_groups: list[list[int]] | None = None,
        out_dir: Path | None = None,
    ):
        out_dir = out_dir or self.out_dir
        manifest = json.loads((out_dir / "media-manifest.json").read_text(encoding="utf-8"))
        request = manifest["request"]
        template = manifest["template"]
        primary_key = (
            "editable_pptx"
            if manifest["expected"]["editable_pptx"]["required"]
            else "notebooklm_pptx"
        )
        primary_preview_dir = manifest["expected"][primary_key]["preview_dir"]
        payloads = {
            "planning/content-plan.json": {
                "schema_version": 1,
                "status": "approved",
                "main_verdict": request["main_verdict"],
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
                "source": manifest["source"]["path"],
                "audience": request["audience"],
                "purpose": request["purpose"],
                "delivery_context": request["delivery_context"],
                "language": request["language"],
                "editability": "editable_pptx"
                if manifest["expected"]["editable_pptx"]["required"]
                else "non_editable_pptx",
                "review_mode": request["review_mode"],
                "output_scope": MODULE.expected_output_scope(manifest),
                "template_mode": template["mode"],
                "template_alias": template.get("alias", ""),
                "privacy_classification": manifest["privacy"]["classification"],
                "network": manifest["privacy"]["network"],
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
                "preview_dir": primary_preview_dir,
                "rendered_slide_count": 2,
                "cjk_checked": True,
                "cjk_passed": cjk_passed,
                "notes": "中文标题和正文显示正常",
            },
        }
        if template["mode"] == "strict_following":
            payloads["qa/template-fidelity.json"] = {
                "schema_version": 1,
                "status": "passed",
                "template_alias": template["alias"],
                "template_sha256": template["sha256"],
                "allowed_fonts": template.get("allowed_fonts", []),
                "expected_editable_charts": expected_editable_charts,
                "expected_native_tables": expected_native_tables,
                "table_pagination_required": table_pagination_required,
                "table_page_groups": table_page_groups or [],
                "notes": "Synthetic Acme fixture passed all template checks",
            }
        for relative_path, payload in payloads.items():
            MODULE.write_json(out_dir / relative_path, payload)

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
        self.assertEqual(manifest["schema_version"], 3)
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

    def validate(self, template_file: str | None = None):
        return MODULE.validate_manifest(
            argparse.Namespace(
                manifest=str(self.out_dir / "media-manifest.json"),
                visual_reviewed=True,
                source_facts_reviewed=True,
                strict=True,
                template_file=template_file,
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

    def test_schema_v3_manifest_requires_nonempty_main_verdict(self):
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

    def test_schema_v2_manifest_remains_strictly_valid_without_v3_contracts(self):
        self.materialize_valid_bundle()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = 2
        manifest.pop("template")
        manifest.pop("privacy")
        manifest.pop("storage")
        MODULE.write_json(manifest_path, manifest)
        contract_path = self.out_dir / "planning/contract-card.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        for field in (
            "template_mode",
            "template_alias",
            "privacy_classification",
            "network",
        ):
            contract.pop(field)
        MODULE.write_json(contract_path, contract)

        report, exit_code = self.validate()
        self.assertEqual(exit_code, 0, report["errors"])
        self.assertEqual(report["status"], "passed")

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

    def test_confidential_strict_template_plan_separates_delivery_and_redacts_template_path(self):
        state_root = self.root / "private-state"
        run_dir = state_root / "runs" / "run-001"
        output_root = self.root / "company-delivery"
        template_path = self.root / "private-templates" / "weekly-report.pptx"
        template_path.parent.mkdir(parents=True)
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        template_hash = MODULE.sha256_file(template_path)

        manifest = self.plan(
            out_dir=str(run_dir),
            provider="local_editable",
            image_count=0,
            infographic=False,
            template_mode="strict_following",
            template_alias="weekly_report",
            template_file=str(template_path),
            template_sha256=template_hash,
            allowed_font=["Aptos", "Noto Sans SC"],
            privacy_classification="confidential",
            network="deny",
            provider_allowlist="local_editable,officecli",
            persist_intermediates="private_state",
            state_root=str(state_root),
            output_root=str(output_root),
        )

        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn(str(template_path), serialized)
        self.assertEqual(manifest["template"]["alias"], "weekly_report")
        self.assertEqual(manifest["template"]["sha256"], template_hash)
        self.assertEqual(manifest["expected"]["editable_pptx"]["base"], "delivery")
        self.assertEqual(manifest["expected"]["prompts"][0]["path"], "prompts/ppt-local.txt")
        self.assertTrue((run_dir / "media-manifest.json").is_file())
        self.assertFalse(output_root.exists())

    def test_confidential_intermediates_cannot_be_redirected_to_delivery(self):
        state_root = self.root / "private-state"
        run_dir = state_root / "runs" / "run-001"
        manifest = self.plan(
            out_dir=str(run_dir),
            provider="local_editable",
            image_count=0,
            infographic=False,
            privacy_classification="confidential",
            network="deny",
            provider_allowlist="local_editable,officecli",
            persist_intermediates="private_state",
            state_root=str(state_root),
            output_root=str(self.root / "delivery"),
        )
        manifest["expected"]["prompts"][0]["base"] = "delivery"
        manifest["expected"]["visual_assets"]["base"] = "delivery"
        errors = []
        MODULE.validate_privacy_contract(manifest, run_dir, errors)
        codes = {item["code"] for item in errors}
        self.assertIn("confidential_intermediate_not_state", codes)
        self.assertIn("confidential_visual_assets_not_state", codes)

    def test_confidential_plan_rejects_relative_output_root(self):
        with self.assertRaisesRegex(ValueError, "absolute output_root"):
            self.plan(
                out_dir=str(self.root / "state" / "runs" / "run-001"),
                provider="local_editable",
                image_count=0,
                infographic=False,
                privacy_classification="confidential",
                network="deny",
                provider_allowlist="local_editable,officecli",
                persist_intermediates="private_state",
                state_root=str(self.root / "state"),
                output_root="relative-delivery",
            )

    def test_confidential_plan_rejects_network_provider(self):
        with self.assertRaisesRegex(ValueError, "network=deny rejects network providers"):
            self.plan(
                out_dir=str(self.root / "state" / "runs" / "run-001"),
                provider="notebooklm",
                image_count=0,
                infographic=False,
                privacy_classification="confidential",
                network="deny",
                provider_allowlist="local_editable,officecli,notebooklm",
                persist_intermediates="private_state",
                state_root=str(self.root / "state"),
                output_root=str(self.root / "delivery"),
            )

    def test_confidential_plan_rejects_network_provider_in_allowlist(self):
        with self.assertRaisesRegex(ValueError, "allowlist cannot include network providers"):
            self.plan(
                out_dir=str(self.root / "state" / "runs" / "run-001"),
                provider="local_editable",
                image_count=0,
                infographic=False,
                privacy_classification="confidential",
                network="deny",
                provider_allowlist="local_editable,officecli,notebooklm",
                persist_intermediates="private_state",
                state_root=str(self.root / "state"),
                output_root=str(self.root / "delivery"),
            )

    def test_confidential_plan_rejects_git_checkout_roots(self):
        checkout = self.root / "repo"
        (checkout / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "output_root cannot be inside a Git checkout"):
            self.plan(
                out_dir=str(self.root / "state" / "runs" / "run-001"),
                provider="local_editable",
                image_count=0,
                infographic=False,
                privacy_classification="confidential",
                network="deny",
                provider_allowlist="local_editable,officecli",
                persist_intermediates="private_state",
                state_root=str(self.root / "state"),
                output_root=str(checkout / "deliveries"),
            )

    def test_strict_template_plan_rejects_hash_mismatch(self):
        template_path = self.root / "template.pptx"
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        with self.assertRaisesRegex(ValueError, "template_sha256 does not match"):
            self.plan(
                provider="local_editable",
                image_count=0,
                infographic=False,
                template_mode="strict_following",
                template_alias="weekly_report",
                template_file=str(template_path),
                template_sha256="0" * 64,
            )

    def test_strict_template_plan_rejects_plain_text_named_pptx(self):
        template_path = self.root / "not-really-a-template.pptx"
        template_path.write_text("not an OOXML package", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "valid PPTX OOXML package"):
            self.plan(
                provider="local_editable",
                image_count=0,
                infographic=False,
                template_mode="strict_following",
                template_alias="weekly_report",
                template_file=str(template_path),
                template_sha256=MODULE.sha256_file(template_path),
            )

    def test_confidential_strict_template_bundle_passes_with_private_state_and_final_delivery(self):
        self.article = ROOT / "tests" / "fixtures" / "article-ppt" / "acme-weekly-report.md"
        state_root = self.root / "private-state"
        run_dir = state_root / "runs" / "acme-001"
        output_root = self.root / "company-delivery"
        output_root.mkdir(parents=True)
        template_path = self.root / "private-templates" / "weekly-report.pptx"
        template_path.parent.mkdir(parents=True)
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        template_hash = MODULE.sha256_file(template_path)
        manifest = self.plan(
            out_dir=str(run_dir),
            provider="local_editable",
            slide_count="2",
            image_count=0,
            infographic=False,
            main_verdict="稳定交付需要先处理测试环境容量风险",
            template_mode="strict_following",
            template_alias="weekly_report",
            template_file=str(template_path),
            template_sha256=template_hash,
            allowed_font=["Aptos", "Arial", "Noto Sans SC"],
            privacy_classification="confidential",
            network="deny",
            provider_allowlist="local_editable,officecli",
            persist_intermediates="private_state",
            state_root=str(state_root),
            output_root=str(output_root),
        )
        write_fake_pptx(
            output_root / manifest["expected"]["editable_pptx"]["path"],
            [
                CHART_TABLE_SLIDE.format(text="本周结论"),
                TABLE_SLIDE.format(text="下周计划"),
            ],
        )
        for index in (1, 2):
            write_png_header(run_dir / f"previews/editable/slide-{index}.png")
        prompt = run_dir / manifest["expected"]["prompts"][0]["path"]
        prompt.parent.mkdir(parents=True)
        prompt.write_text("Use the verified private template without network providers.\n", encoding="utf-8")
        self.materialize_quality_contracts(
            out_dir=run_dir,
            expected_editable_charts=1,
            expected_native_tables=2,
            table_pagination_required=True,
            table_page_groups=[[1, 2]],
        )

        report, exit_code = MODULE.validate_manifest(
            argparse.Namespace(
                manifest=str(run_dir / "media-manifest.json"),
                visual_reviewed=True,
                source_facts_reviewed=True,
                strict=True,
                template_file=str(template_path),
            )
        )
        self.assertEqual(exit_code, 0, report["errors"])
        self.assertEqual(report["status"], "passed")
        self.assertFalse((run_dir / manifest["expected"]["editable_pptx"]["path"]).exists())

    def test_template_fidelity_rejects_overflow_and_manifest_template_path(self):
        template_path = self.root / "template.pptx"
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        manifest = self.plan(
            provider="local_editable",
            image_count=0,
            infographic=False,
            template_mode="strict_following",
            template_alias="weekly_report",
            template_file=str(template_path),
            template_sha256=MODULE.sha256_file(template_path),
        )
        write_fake_pptx(
            self.out_dir / manifest["expected"]["editable_pptx"]["path"],
            [EDITABLE_SLIDE.format(text="本周结论"), OVERFLOW_SLIDE],
        )
        for index in (1, 2):
            write_png_header(self.out_dir / f"previews/editable/slide-{index}.png")
        prompt = self.out_dir / manifest["expected"]["prompts"][0]["path"]
        prompt.parent.mkdir(parents=True)
        prompt.write_text("Use the Acme synthetic template.\n", encoding="utf-8")
        self.materialize_quality_contracts()
        manifest_path = self.out_dir / "media-manifest.json"
        manifest["template"]["template_path"] = str(template_path)
        MODULE.write_json(manifest_path, manifest)

        report, exit_code = self.validate(str(template_path))
        self.assertEqual(exit_code, 1)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("template_fidelity_overflow", codes)
        self.assertIn("manifest_template_path_disclosed", codes)

    def test_strict_validation_rechecks_template_bytes_after_planning(self):
        template_path = self.root / "template.pptx"
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        manifest = self.plan(
            provider="local_editable",
            image_count=0,
            infographic=False,
            template_mode="strict_following",
            template_alias="weekly_report",
            template_file=str(template_path),
            template_sha256=MODULE.sha256_file(template_path),
        )
        template_path.write_bytes(template_path.read_bytes() + b"changed-after-plan")
        errors = []
        warnings = []
        MODULE.validate_template_source(
            manifest,
            argparse.Namespace(template_file=str(template_path), strict=True),
            errors,
            warnings,
        )
        self.assertIn("template_source_sha256_mismatch", {item["code"] for item in errors})
        self.assertEqual(warnings, [])

    def test_template_fidelity_contract_covers_every_weekly_report_gate(self):
        manifest = {
            "template": {
                "mode": "strict_following",
                "alias": "weekly_report",
                "sha256": "a" * 64,
                "allowed_fonts": ["Aptos", "Noto Sans SC"],
            }
        }
        valid = {
            "status": "passed",
            "template_alias": "weekly_report",
            "template_sha256": "a" * 64,
            "allowed_fonts": ["Aptos", "Noto Sans SC"],
            "expected_editable_charts": 1,
            "expected_native_tables": 2,
            "table_pagination_required": True,
            "table_page_groups": [[1, 2]],
        }
        template_inspection = {
            "valid_ooxml": True,
            "slide_size": [12192000, 6858000],
            "master_digest": "master",
            "layout_digest": "layout",
        }
        output_inspection = {
            **template_inspection,
            "fonts": ["Aptos"],
            "chart_references": 1,
            "bound_chart_count": 1,
            "unbound_chart_references": 0,
            "chart_parts": 1,
            "table_count": 2,
            "slide_table_counts": {"1": 1, "2": 1},
            "overflow_count": 0,
            "orphan_connector_count": 0,
        }
        cases = {
            "slide_size": ([100, 100], "template_fidelity_slide_size_mismatch"),
            "master_digest": ("changed", "template_fidelity_masters_mismatch"),
            "layout_digest": ("changed", "template_fidelity_layouts_mismatch"),
            "fonts": (["Comic Sans MS"], "template_fidelity_unexpected_fonts"),
            "bound_chart_count": (0, "template_fidelity_editable_charts_missing"),
            "unbound_chart_references": (1, "template_fidelity_unbound_charts"),
            "table_count": (1, "template_fidelity_native_tables_missing"),
            "slide_table_counts": ({"1": 1, "2": 0}, "template_fidelity_table_pagination_invalid"),
            "overflow_count": (1, "template_fidelity_overflow"),
            "orphan_connector_count": (1, "template_fidelity_orphan_connectors"),
        }
        for field, (value, expected_code) in cases.items():
            with self.subTest(field=field):
                inspection = dict(output_inspection)
                inspection[field] = value
                errors = []
                MODULE.validate_template_fidelity(
                    dict(valid), manifest, template_inspection, inspection, errors
                )
                self.assertIn(expected_code, {item["code"] for item in errors})

        errors = []
        invalid_declaration = dict(valid)
        invalid_declaration["allowed_fonts"] = ["Comic Sans MS"]
        MODULE.validate_template_fidelity(
            invalid_declaration, manifest, template_inspection, output_inspection, errors
        )
        self.assertIn(
            "template_fidelity_allowed_fonts_mismatch",
            {item["code"] for item in errors},
        )

    def test_layout_digest_ignores_volatile_relationship_attributes(self):
        layout_a = """<?xml version="1.0" encoding="UTF-8"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
              xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree><p:pic><p:blipFill><a:blip r:embed="Rvolatile-a"/></p:blipFill></p:pic></p:spTree></p:cSld>
</p:sldLayout>
"""
        layout_b = layout_a.replace("Rvolatile-a", "Rvolatile-b")
        first = self.root / "digest-a.pptx"
        second = self.root / "digest-b.pptx"
        for path, payload in ((first, layout_a), (second, layout_b)):
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("ppt/slideLayouts/slideLayout1.xml", payload)
        with zipfile.ZipFile(first) as archive:
            digest_a = MODULE.ooxml_parts_digest(
                archive, ["ppt/slideLayouts/slideLayout1.xml"]
            )
        with zipfile.ZipFile(second) as archive:
            digest_b = MODULE.ooxml_parts_digest(
                archive, ["ppt/slideLayouts/slideLayout1.xml"]
            )
        self.assertEqual(digest_a, digest_b)

    def test_config_uses_validator_host_enum(self):
        config = (
            ROOT / "skills" / "soia-pkm-transform-article-ppt" / "assets" / "config.example.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("apple_keynote", config)
        self.assertNotIn("| keynote |", config)
        self.assertIn("schema_version: 2", config)
        self.assertIn("mode: none", config)
        self.assertIn("classification: public", config)
        self.assertIn("provider_allowlist:", config)
        self.assertIn("state_root:", config)
        self.assertIn("output_root:", config)
        self.assertIn(
            "soia-open-pkm-vault-skills/soia-pkm/soia-pkm-transform-article-ppt",
            config,
        )

    def test_private_config_env_resolves_template_and_cli_takes_precedence(self):
        template_path = self.root / "private-templates" / "weekly-report.pptx"
        template_path.parent.mkdir(parents=True)
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        template_hash = MODULE.sha256_file(template_path)
        state_root = self.root / "private-state"
        run_dir = state_root / "runs" / "run-001"
        output_root = self.root / "delivery"
        config_path = self.root / "config.yml"
        config_path.write_text(
            f"""schema_version: 2
defaults:
  provider: notebooklm
  image_count: 0
  infographic: false
template:
  mode: strict_following
  alias: weekly_report
  path: {template_path}
  sha256: {template_hash}
  allowed_fonts: [Aptos, Noto Sans SC]
privacy:
  classification: confidential
  network: deny
  provider_allowlist:
    - local_editable
    - officecli
  persist_intermediates: private_state
paths:
  state_root: {state_root}
  output_root: {output_root}
""",
            encoding="utf-8",
        )
        args = MODULE.build_parser().parse_args(
            [
                "plan",
                "--article",
                str(self.article),
                "--out-dir",
                str(run_dir),
                "--provider",
                "local_editable",
                "--main-verdict",
                "本地隔离优先",
            ]
        )
        with mock.patch.dict(
            "os.environ", {MODULE.CONFIG_ENV_VAR: str(config_path)}, clear=False
        ):
            config = MODULE.load_private_config(args)
        MODULE.apply_plan_config(args, config)
        manifest = MODULE.build_manifest(args)

        self.assertEqual(manifest["request"]["provider"], "local_editable")
        self.assertEqual(manifest["template"]["alias"], "weekly_report")
        self.assertEqual(manifest["template"]["sha256"], template_hash)
        self.assertEqual(manifest["privacy"]["classification"], "confidential")
        self.assertEqual(manifest["privacy"]["provider_allowlist"], ["local_editable", "officecli"])
        self.assertNotIn(str(template_path), json.dumps(manifest, ensure_ascii=False))

        errors = []
        warnings = []
        inspection = MODULE.validate_template_source(
            manifest,
            argparse.Namespace(
                template_file=None,
                strict=True,
                _private_config=config,
            ),
            errors,
            warnings,
        )
        self.assertTrue(inspection and inspection["valid_ooxml"])
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_private_config_template_binding_rejects_alias_drift(self):
        template_path = self.root / "template.pptx"
        write_fake_pptx(template_path, [EDITABLE_SLIDE.format(text="Acme template")])
        manifest = {
            "template": {
                "mode": "strict_following",
                "alias": "weekly_report",
                "sha256": MODULE.sha256_file(template_path),
            }
        }
        config = {
            "schema_version": 2,
            "template": {
                "alias": "different_report",
                "path": str(template_path),
                "sha256": manifest["template"]["sha256"],
            },
        }
        errors = []
        MODULE.validate_template_source(
            manifest,
            argparse.Namespace(template_file=None, strict=True, _private_config=config),
            errors,
            [],
        )
        self.assertIn(
            "template_config_binding_mismatch",
            {item["code"] for item in errors},
        )


if __name__ == "__main__":
    unittest.main()

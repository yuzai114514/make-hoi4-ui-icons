from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_ROOT = Path(__file__).resolve().parents[1]
COMPOSER_PATH = SKILL_ROOT / "scripts" / "compose_layers.py"
FINALIZER_PATH = SKILL_ROOT / "scripts" / "finalize_icon.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


composer = load_module("compose_layers_under_test", COMPOSER_PATH)
finalizer = load_module("finalize_icon_under_test", FINALIZER_PATH)


class LayeredTfrTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "layers" / "themes").mkdir(parents=True)
        (self.root / "layers" / "effects").mkdir(parents=True)
        self.make_source(
            self.root / "layers" / "themes" / "geography.png",
            (20, 155, 188, 255),
            "ellipse",
        )
        self.make_source(
            self.root / "layers" / "themes" / "fleet.png",
            (120, 24, 34, 255),
            "rectangle",
        )
        self.make_source(
            self.root / "layers" / "effects" / "radar.png",
            (255, 40, 56, 190),
            "line",
        )
        (self.root / "brief.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "input_mode": "human",
                    "style": "tfr",
                    "icon_type": "focus",
                    "profile": "focus-tfr",
                    "focus_name": "海峡没有退路",
                    "focus_description": "舰队封锁海峡，雷达警报逼近。",
                    "input_basis": {
                        "focus_name": "provided",
                        "focus_description": "provided",
                    },
                    "themes": [
                        {
                            "id": "strait-geography",
                            "name": "海峡地缘",
                            "role": "background",
                            "evidence": "海峡",
                            "subject": "海峡两岸地形",
                            "motifs": ["海峡", "海岸线"],
                            "placement": "背景",
                            "palette": "冷青",
                            "prompt": "独立生成海峡地形，不含其他主题。",
                        },
                        {
                            "id": "blockade-fleet",
                            "name": "封锁舰队",
                            "role": "primary",
                            "evidence": "舰队封锁",
                            "subject": "现代舰队封锁阵形",
                            "motifs": ["舰队", "封锁阵形"],
                            "placement": "前景",
                            "palette": "深钢与红光",
                            "prompt": "独立生成现代舰队，不含地图或雷达。",
                        },
                    ],
                    "effects": [
                        {
                            "id": "radar-approach",
                            "name": "雷达逼近",
                            "kind": "narrative",
                            "evidence": "雷达警报逼近",
                            "subject": "雷达扫描弧和光点",
                            "placement": "上方覆盖",
                            "palette": "警报红",
                            "prompt": "独立生成雷达发光特效。",
                        }
                    ],
                    "constraints": ["无文字", "底部40像素透明"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.spec_path = self.root / "composition.json"
        self.write_spec(self.valid_spec())

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def make_source(path: Path, color: tuple[int, int, int, int], shape: str) -> None:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        if shape == "ellipse":
            draw.ellipse((7, 8, 57, 55), fill=color)
        elif shape == "rectangle":
            draw.rounded_rectangle((8, 16, 56, 49), radius=5, fill=color)
        elif shape == "line":
            draw.arc((4, 4, 60, 60), 190, 345, fill=color, width=4)
            draw.line((10, 48, 52, 16), fill=color, width=3)
        else:
            raise ValueError(shape)
        image.save(path)

    def valid_spec(self) -> dict:
        return {
            "schema_version": 1,
            "style": "tfr",
            "icon_type": "focus",
            "profile": "focus-tfr",
            "brief": "brief.json",
            "canvas": {"width": 180, "height": 150, "safe_bottom": 40},
            "themes": [
                {
                    "id": "strait-geography",
                    "name": "海峡地缘",
                    "role": "background",
                    "evidence": "海峡",
                    "source": "layers/themes/geography.png",
                    "source_asset_ids": [],
                    "z": 10,
                    "transform": {
                        "x": 20,
                        "y": 18,
                        "width": 64,
                        "height": 58,
                        "rotation": 0,
                    },
                    "opacity": 1.0,
                    "blend": "normal",
                    "boundary": {
                        "primary": {"type": "feather", "radius": 1.5},
                        "support": {
                            "type": "shadow",
                            "offset": [2, 2],
                            "blur": 2,
                            "color": "#102b37",
                            "opacity": 0.55,
                        },
                    },
                },
                {
                    "id": "blockade-fleet",
                    "name": "封锁舰队",
                    "role": "primary",
                    "evidence": "舰队封锁",
                    "source": "layers/themes/fleet.png",
                    "source_asset_ids": [],
                    "z": 20,
                    "transform": {
                        "x": 92,
                        "y": 28,
                        "width": 56,
                        "height": 50,
                        "rotation": 0,
                    },
                    "opacity": 1.0,
                    "blend": "normal",
                    "boundary": {
                        "primary": {
                            "type": "outline",
                            "width": 2,
                            "color": "#ff334d",
                            "opacity": 0.9,
                        },
                        "support": {
                            "type": "shadow",
                            "offset": [2, 2],
                            "blur": 2,
                            "color": "#16070b",
                            "opacity": 0.65,
                        },
                    },
                    "finish": {
                        "relief": {"depth": 1, "opacity": 0.18},
                        "rim": {"width": 1, "color": "#ffd7d7", "opacity": 0.12},
                    },
                },
            ],
            "effects": [
                {
                    "id": "radar-approach",
                    "name": "雷达逼近",
                    "kind": "narrative",
                    "source": "layers/effects/radar.png",
                    "source_asset_ids": [],
                    "z": 30,
                    "transform": {
                        "x": 52,
                        "y": 8,
                        "width": 72,
                        "height": 60,
                        "rotation": 0,
                    },
                    "opacity": 0.75,
                    "blend": "screen",
                }
            ],
        }

    def write_spec(self, payload: dict) -> None:
        self.spec_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def compose(self, *, overwrite: bool = False) -> tuple[Path, Path]:
        output = self.root / "composite-source.png"
        report = self.root / "composite-source.layers.json"
        command = [
            sys.executable,
            str(COMPOSER_PATH),
            "compose",
            "--spec",
            str(self.spec_path),
            "--manifest-root",
            str(self.root),
            "--output",
            str(output),
            "--effects-dir",
            str(self.root / "layers" / "effects"),
            "--qa-dir",
            str(self.root / "qa"),
            "--report",
            str(report),
        ]
        if overwrite:
            command.append("--overwrite")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return output, report

    def test_compose_exports_layers_and_is_deterministic(self) -> None:
        output, report_path = self.compose()
        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (180, 150))
            self.assertEqual(image.getchannel("A").crop((0, 110, 180, 150)).getextrema()[1], 0)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["validation"]["ok"])
        self.assertEqual(report["validation"]["theme_count"], 2)
        self.assertEqual(report["validation"]["key_green_pixels"], 0)
        self.assertEqual(report["validation"]["key_magenta_pixels"], 0)
        structural = [layer for layer in report["layers"] if layer["kind"] == "structural-effect"]
        self.assertGreaterEqual(len(structural), 6)
        for layer in structural:
            path = self.root / layer["path"]
            self.assertTrue(path.is_file())
            with Image.open(path) as effect:
                self.assertEqual(effect.mode, "RGBA")
                self.assertEqual(effect.size, (180, 150))
                self.assertIsNotNone(effect.getchannel("A").getbbox())
        for name in ("layer-map", "light", "dark", "contact-sheet"):
            path = self.root / report["qa"][name]
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.name, "final")
        for theme_id in ("strait-geography", "blockade-fleet"):
            name = f"theme-{theme_id}"
            final_preview = self.root / report["qa"][name]
            self.assertTrue(final_preview.is_file())
            self.assertEqual(final_preview.parent.name, "final")
            material_name = f"material-theme-{theme_id}"
            material_preview = self.root / report["qa"][material_name]
            self.assertTrue(material_preview.is_file())
            self.assertEqual(material_preview.parent.name, "materials")
            with Image.open(material_preview) as material:
                self.assertEqual(material.mode, "RGB")
                self.assertEqual(material.size, (360, 150))
        effect_preview = self.root / report["qa"]["material-effect-radar-approach"]
        self.assertTrue(effect_preview.is_file())
        self.assertEqual(effect_preview.parent.name, "materials")

        outline_record = next(
            layer
            for layer in report["layers"]
            if layer["owner_id"] == "blockade-fleet" and layer["role"] == "outline"
        )
        with Image.open(self.root / outline_record["path"]) as outline:
            outline_pixel = next(
                (x, y)
                for y in range(outline.height)
                for x in range(outline.width)
                if outline.getpixel((x, y))[3] > 0
            )
        material_path = self.root / report["qa"]["material-theme-blockade-fleet"]
        final_path = self.root / report["qa"]["theme-blockade-fleet"]
        with Image.open(material_path) as material, Image.open(final_path) as final_preview:
            x, y = outline_pixel
            self.assertEqual(material.getpixel((x, y)), (238, 238, 238))
            self.assertEqual(material.getpixel((x + 180, y)), (22, 24, 28))
            self.assertNotEqual(final_preview.getpixel((x, y)), (22, 24, 28))

        first_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        second_output, second_report = self.compose()
        self.assertTrue(second_output.with_name("composite-source-v2.png").is_file())
        versioned = second_output.with_name("composite-source-v2.png")
        self.assertEqual(first_hash, hashlib.sha256(versioned.read_bytes()).hexdigest())
        self.assertTrue(second_report.with_name("composite-source-v2.layers.json").is_file())

    def test_overwrite_cleans_only_legacy_root_qa_previews(self) -> None:
        output, report_path = self.compose()
        qa_root = self.root / "qa"
        legacy_names = (
            "light.png",
            "light-v10.png",
            "contact-sheet-v100.png",
            "theme-blockade-fleet.png",
            "material-theme-blockade-fleet-v2.png",
            "theme-retired.png",
        )
        for name in legacy_names:
            (qa_root / name).write_bytes(b"legacy preview")
        previous_report = json.loads(report_path.read_text(encoding="utf-8"))
        previous_report["qa"]["theme-retired"] = "qa/theme-retired.png"
        report_path.write_text(
            json.dumps(previous_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        preserved_names = (
            "artist-notes.png",
            "theme-blockade-fleet-v1.png",
            "material-theme-fleet-v1.png",
            "material-theme-fleet-v01.png",
            "material-effect-radar-v1.png",
            "light-v٢.png",
        )
        for name in preserved_names:
            (qa_root / name).write_bytes(b"keep")

        overwritten_output, overwritten_report = self.compose(overwrite=True)

        self.assertEqual(overwritten_output, output)
        self.assertEqual(overwritten_report, report_path)
        for name in legacy_names:
            self.assertFalse((qa_root / name).exists())
        for name in preserved_names:
            self.assertEqual((qa_root / name).read_bytes(), b"keep")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(all((self.root / path).parent.parent == qa_root for path in report["qa"].values()))

    def test_rejects_single_theme(self) -> None:
        spec = self.valid_spec()
        spec["themes"] = spec["themes"][:1]
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "two to four"):
            composer.render_spec(self.spec_path, self.root)

    def test_spec_paths_are_relative_to_the_spec_directory(self) -> None:
        package = self.root / "nested-package"
        (package / "layers" / "themes").mkdir(parents=True)
        (package / "layers" / "effects").mkdir(parents=True)
        for name in ("geography.png", "fleet.png"):
            shutil.copy2(
                self.root / "layers" / "themes" / name,
                package / "layers" / "themes" / name,
            )
        shutil.copy2(
            self.root / "layers" / "effects" / "radar.png",
            package / "layers" / "effects" / "radar.png",
        )
        shutil.copy2(self.root / "brief.json", package / "brief.json")
        nested_spec = package / "composition.json"
        nested_spec.write_text(
            json.dumps(self.valid_spec(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _, report, _, _ = composer.render_spec(nested_spec, self.root)
        self.assertTrue(report["validation"]["ok"])
        self.assertEqual(
            report["themes"][0]["source"],
            "nested-package/layers/themes/geography.png",
        )

    def test_rejects_missing_boundary(self) -> None:
        spec = self.valid_spec()
        del spec["themes"][0]["boundary"]
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "boundary"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_theme_not_grounded_in_brief(self) -> None:
        spec = self.valid_spec()
        spec["themes"][1]["id"] = "invented-theme"
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "not grounded"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_theme_or_effect_omitted_from_brief_contract(self) -> None:
        brief = json.loads((self.root / "brief.json").read_text(encoding="utf-8"))
        brief["themes"].append(
            {
                "id": "blackout-port",
                "name": "熄灭港口",
                "role": "secondary",
                "evidence": "港口灯火熄灭",
                "subject": "熄灯港口",
                "motifs": ["港口"],
                "placement": "下方",
                "palette": "深灰",
                "prompt": "独立生成熄灯港口。",
            }
        )
        (self.root / "brief.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "missing themes"):
            composer.render_spec(self.spec_path, self.root)

        brief["themes"].pop()
        brief["effects"].append(
            {
                "id": "warning-flash",
                "name": "警报闪光",
                "kind": "narrative",
                "evidence": "警报闪光",
                "subject": "闪光",
                "placement": "上方",
                "palette": "红色",
                "prompt": "独立生成警报闪光。",
            }
        )
        (self.root / "brief.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "missing effects"):
            composer.render_spec(self.spec_path, self.root)

    def test_validates_human_and_ai_resolved_brief_contracts(self) -> None:
        brief = json.loads((self.root / "brief.json").read_text(encoding="utf-8"))
        brief["focus_name"] = None
        brief["input_basis"]["focus_name"] = "missing"
        (self.root / "brief.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )
        _, report, _, _ = composer.render_spec(self.spec_path, self.root)
        self.assertTrue(report["validation"]["ok"])

        brief["input_mode"] = "ai"
        brief["focus_name"] = "海峡没有退路"
        brief["input_basis"]["focus_name"] = "provided"
        del brief["themes"][0]["prompt"]
        (self.root / "brief.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, r"brief\.themes\[1\]\.prompt"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_path_escape(self) -> None:
        spec = self.valid_spec()
        spec["themes"][0]["source"] = "../outside.png"
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "safe manifest-root-relative"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_invalid_blend(self) -> None:
        spec = self.valid_spec()
        spec["effects"][0]["blend"] = "overlay"
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "blend"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_magenta_chroma_key_residue(self) -> None:
        magenta = self.root / "layers" / "effects" / "magenta.png"
        self.make_source(magenta, (255, 0, 255, 255), "line")
        spec = self.valid_spec()
        spec["effects"][0]["source"] = "layers/effects/magenta.png"
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "chroma-key-magenta"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_empty_source(self) -> None:
        empty = self.root / "layers" / "themes" / "empty.png"
        Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(empty)
        spec = self.valid_spec()
        spec["themes"][0]["source"] = "layers/themes/empty.png"
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "no visible pixels"):
            composer.render_spec(self.spec_path, self.root)

    def test_rejects_title_safe_intrusion(self) -> None:
        spec = self.valid_spec()
        spec["themes"][1]["transform"]["y"] = 89
        self.write_spec(spec)
        with self.assertRaisesRegex(ValueError, "exceed content area"):
            composer.render_spec(self.spec_path, self.root)

    def test_preserve_canvas_manifest_and_safe_area_validation(self) -> None:
        output, report = self.compose()
        final = self.root / "final.png"
        manifest = self.root / "manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(output),
                "--output",
                str(final),
                "--manifest",
                str(manifest),
                "--manifest-root",
                str(self.root),
                "--profile",
                "focus-tfr",
                "--layout",
                "preserve-canvas",
                "--style",
                "tfr",
                "--icon-type",
                "focus",
                "--brief",
                str(self.root / "brief.json"),
                "--composition",
                str(self.spec_path),
                "--layer-report",
                str(report),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["layout"], "preserve-canvas")
        self.assertEqual(payload["brief_file"], "brief.json")
        self.assertEqual(payload["composition_file"], "composition.json")
        self.assertEqual(payload["layer_validation"]["theme_count"], 2)
        self.assertGreater(len(payload["layers"]), 2)

        bad = Image.new("RGBA", (180, 150), (0, 0, 0, 0))
        bad.putpixel((20, 130), (255, 255, 255, 255))
        bad_path = self.root / "bad-safe-bottom.png"
        bad.save(bad_path)
        report_payload = finalizer.validate_image(
            bad_path, finalizer.PROFILES["focus-tfr"], 4
        )
        self.assertFalse(report_payload["ok"])
        self.assertIn("title-safe area", " ".join(report_payload["errors"]))

        rejected_output = self.root / "bad-final.png"
        rejected = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(bad_path),
                "--output",
                str(rejected_output),
                "--manifest-root",
                str(self.root),
                "--profile",
                "focus-tfr",
                "--layout",
                "preserve-canvas",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(rejected_output.exists())

        faint = Image.new("RGBA", (180, 150), (0, 0, 0, 0))
        faint.putpixel((20, 20), (255, 255, 255, 255))
        faint.putpixel((20, 130), (255, 255, 255, 1))
        faint_path = self.root / "faint-safe-bottom.png"
        faint.save(faint_path)
        faint_report = finalizer.validate_image(
            faint_path, finalizer.PROFILES["focus-tfr"], 4
        )
        self.assertFalse(faint_report["ok"])
        self.assertEqual(faint_report["safe_bottom_alpha_max"], 1)

        faint_output = self.root / "faint-final.png"
        faint_rejected = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(faint_path),
                "--output",
                str(faint_output),
                "--manifest-root",
                str(self.root),
                "--profile",
                "focus-tfr",
                "--layout",
                "preserve-canvas",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(faint_rejected.returncode, 0)
        self.assertFalse(faint_output.exists())

    def test_legacy_fit_content_and_gfx_remain_available(self) -> None:
        source = self.root / "legacy.png"
        self.make_source(source, (218, 177, 70, 255), "ellipse")
        final = self.root / "legacy-final.png"
        manifest = self.root / "legacy-manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(source),
                "--output",
                str(final),
                "--manifest",
                str(manifest),
                "--manifest-root",
                str(self.root),
                "--profile",
                "focus",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(final) as image:
            self.assertEqual(image.size, (100, 88))
            self.assertEqual(image.mode, "RGBA")
        self.assertEqual(
            json.loads(manifest.read_text(encoding="utf-8"))["layout"], "fit-content"
        )

        gfx = self.root / "test.gfx"
        gfx_result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "gfx",
                "--sprite-name",
                "GFX_test_layered_tfr",
                "--texture-path",
                "gfx/interface/goals/test.png",
                "--output",
                str(gfx),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(gfx_result.returncode, 0, gfx_result.stderr)
        self.assertIn('name = "GFX_test_layered_tfr"', gfx.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

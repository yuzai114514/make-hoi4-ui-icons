from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILD_INDEX_PATH = SKILL_ROOT / "scripts" / "build_index.py"
SEARCH_PATH = SKILL_ROOT / "scripts" / "search_assets.py"
FINALIZER_PATH = SKILL_ROOT / "scripts" / "finalize_icon.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


finalizer = load_module("finalize_icon_legacy_regression", FINALIZER_PATH)


class LegacyWorkflowRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        image = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (7, 8, 65, 63), radius=8, fill=(74, 112, 168, 255)
        )
        draw.ellipse((20, 18, 52, 50), fill=(222, 174, 72, 255))
        image.save(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_finalizer(
        self, name: str, style: str, icon_type: str, profile_args: list[str]
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        output = self.root / f"{name}.png"
        manifest = self.root / f"{name}.manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(self.source),
                "--output",
                str(output),
                "--manifest",
                str(manifest),
                "--manifest-root",
                str(self.root),
                "--creation-mode",
                "generated",
                "--style",
                style,
                "--icon-type",
                icon_type,
                *profile_args,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result, output, manifest

    def write_records(self, name: str, record: dict) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(
            json.dumps([record], ensure_ascii=False), encoding="utf-8"
        )
        return path

    @staticmethod
    def source_record(
        authorization: str,
        use: str,
        credit: str | None = None,
    ) -> dict:
        return {
            "asset_id": "test-asset",
            "source": "素材库/国策图标/test.png",
            "role": "finished",
            "authorization": authorization,
            "use": use,
            "credit": credit,
        }

    def test_vanilla_tno_and_red_flood_finalization_remain_available(self) -> None:
        cases = [
            ("vanilla-focus", "vanilla", "focus", ["--profile", "focus"], (100, 88)),
            ("tno-idea", "tno", "idea", ["--profile", "idea"], (60, 68)),
            (
                "red-flood-focus",
                "red-flood",
                "focus",
                ["--profile", "custom", "--width", "150", "--height", "130"],
                (150, 130),
            ),
        ]
        for name, style, icon_type, profile_args, expected_size in cases:
            with self.subTest(style=style):
                result, output, manifest = self.run_finalizer(
                    name, style, icon_type, profile_args
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                with Image.open(output) as image:
                    self.assertEqual(image.mode, "RGBA")
                    self.assertEqual(image.size, expected_size)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                self.assertEqual(payload["style"], style)
                self.assertEqual(payload["icon_type"], icon_type)
                self.assertTrue(payload["validation"]["ok"])
                self.assertEqual(payload["validation"]["key_green_pixels"], 0)
                self.assertEqual(payload["validation"]["key_magenta_pixels"], 0)

    def test_reuse_and_authorization_matrix_remain_fail_closed(self) -> None:
        approved_path = self.write_records(
            "approved", self.source_record("approved", "reused")
        )
        records, credits = finalizer.load_source_records(
            str(approved_path), self.root, "reused"
        )
        self.assertEqual(records[0]["authorization"], "approved")
        self.assertEqual(credits, [])

        output = self.root / "approved-reuse.png"
        manifest = self.root / "approved-reuse.manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(self.source),
                "--output",
                str(output),
                "--manifest",
                str(manifest),
                "--manifest-root",
                str(self.root),
                "--profile",
                "custom",
                "--width",
                "72",
                "--height",
                "72",
                "--padding",
                "0",
                "--no-trim",
                "--creation-mode",
                "reused",
                "--source-records",
                str(approved_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.source) as source, Image.open(output) as reused:
            self.assertIsNone(
                ImageChops.difference(
                    source.convert("RGBA"), reused.convert("RGBA")
                ).getbbox()
            )

        missing_credit = self.write_records(
            "missing-credit",
            self.source_record("credit_required", "reused"),
        )
        with self.assertRaisesRegex(ValueError, "creator credit"):
            finalizer.load_source_records(str(missing_credit), self.root, "reused")

        credited = self.write_records(
            "credited",
            self.source_record("credit_required", "reused", "Creator"),
        )
        _, credits = finalizer.load_source_records(
            str(credited), self.root, "reused"
        )
        self.assertEqual(credits, ["Creator"])

        unknown = self.write_records(
            "unknown", self.source_record("unknown", "reused")
        )
        with self.assertRaisesRegex(ValueError, "cannot reused"):
            finalizer.load_source_records(str(unknown), self.root, "reused")

        forbidden = self.write_records(
            "forbidden", self.source_record("forbidden", "reference_only")
        )
        with self.assertRaisesRegex(ValueError, "must use 'excluded'"):
            finalizer.load_source_records(str(forbidden), self.root, "generated")

        direct_generated = self.write_records(
            "direct-generated", self.source_record("approved", "transformed")
        )
        with self.assertRaisesRegex(ValueError, "cannot include"):
            finalizer.load_source_records(
                str(direct_generated), self.root, "generated"
            )

    def test_key_green_and_magenta_are_rejected_before_output(self) -> None:
        keyed = Image.new("RGBA", (100, 88), (0, 0, 0, 0))
        draw = ImageDraw.Draw(keyed)
        draw.rectangle((10, 10, 40, 40), fill=(80, 100, 120, 255))
        keyed.putpixel((20, 20), (0, 255, 0, 255))
        keyed.putpixel((21, 20), (255, 0, 255, 255))
        keyed_path = self.root / "keyed.png"
        keyed.save(keyed_path)

        report = finalizer.validate_image(
            keyed_path, finalizer.PROFILES["focus"], 4
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["key_green_pixels"], 1)
        self.assertEqual(report["key_magenta_pixels"], 1)

        output = self.root / "keyed-final.png"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(keyed_path),
                "--output",
                str(output),
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
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_focus_tfr_safe_bottom_cannot_be_reduced(self) -> None:
        image = Image.new("RGBA", (180, 150), (0, 0, 0, 0))
        image.putpixel((20, 20), (255, 255, 255, 255))
        image.putpixel((20, 130), (255, 80, 80, 255))
        source = self.root / "unsafe-focus-tfr.png"
        image.save(source)
        output = self.root / "unsafe-focus-tfr-final.png"
        result = subprocess.run(
            [
                sys.executable,
                str(FINALIZER_PATH),
                "finalize",
                "--input",
                str(source),
                "--output",
                str(output),
                "--manifest-root",
                str(self.root),
                "--profile",
                "focus-tfr",
                "--layout",
                "preserve-canvas",
                "--safe-bottom",
                "0",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 40", result.stderr)
        self.assertFalse(output.exists())

    def test_mini_library_build_search_integration(self) -> None:
        library = self.root / "library"
        icon_dir = library / "素材库" / "国策图标"
        icon_dir.mkdir(parents=True)
        library_icon = icon_dir / "Modern Fleet.png"
        with Image.open(self.source) as source:
            source.save(library_icon)
        index = self.root / "library-index.jsonl"
        summary = self.root / "library-summary.json"
        utf8_env = dict(os.environ)
        utf8_env["PYTHONUTF8"] = "1"
        build = subprocess.run(
            [
                sys.executable,
                str(BUILD_INDEX_PATH),
                "--library-root",
                str(library),
                "--output",
                str(index),
                "--summary",
                str(summary),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=utf8_env,
        )
        self.assertEqual(build.returncode, 0, build.stderr)
        self.assertTrue(index.is_file())
        self.assertTrue(summary.is_file())

        search = subprocess.run(
            [
                sys.executable,
                str(SEARCH_PATH),
                "--index",
                str(index),
                "--query",
                "Modern Fleet",
                "--icon-type",
                "focus",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=utf8_env,
        )
        self.assertEqual(search.returncode, 0, search.stderr)
        results = json.loads(search.stdout)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(
            results[0]["path"], "素材库/国策图标/Modern Fleet.png"
        )


if __name__ == "__main__":
    unittest.main()

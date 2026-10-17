from __future__ import annotations

import contextlib
import io
import itertools
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scaffold


class ScaffoldLogicTest(unittest.TestCase):
    def test_render_replaces_only_known_generator_variables(self) -> None:
        ctx = scaffold.build_context(
            "demo-app", "com.example.demoapp", "0.2.0", 18080, 15173, 18081, "demo_app"
        )

        rendered = scaffold.render(
            "${PROJECT_NAME} ${UNKNOWN} ${demoapp.jwt.secret} ${1:-} ${APP_VERSION}",
            ctx,
        )

        self.assertEqual(
            rendered,
            "demo-app ${UNKNOWN} ${demoapp.jwt.secret} ${1:-} ${APP_VERSION}",
        )

    def test_build_context_derives_names_and_composite_values(self) -> None:
        ctx = scaffold.build_context(
            "demo-app", "com.example.demoapp", "0.2.0", 18080, 15173, 18081, "demo_app"
        )

        self.assertEqual(ctx["APP_CLASS"], "DemoApp")
        self.assertEqual(ctx["PACKAGE_PATH"], "com/example/demoapp")
        self.assertEqual(ctx["APP_ENV_PREFIX"], "DEMOAPP")
        self.assertEqual(ctx["JWT_SECRET_ANNOTATION"], "${demoapp.jwt.secret}")
        self.assertIn("${DEMOAPP_JWT_SECRET:", ctx["JWT_SECRET_YAML"])

    def test_input_validation_boundaries(self) -> None:
        self.assertEqual(scaffold.valid_port("1"), 1)
        self.assertEqual(scaffold.valid_port("65535"), 65535)
        self.assertIsNone(scaffold.valid_port("0"))
        self.assertIsNone(scaffold.valid_port("65536"))
        self.assertIsNone(scaffold.valid_port("abc"))

        self.assertIsNone(scaffold.package_error("com.example.demoapp"))
        self.assertIn("关键字", scaffold.package_error("com.example.class"))
        self.assertIsNotNone(scaffold.package_error("com..demoapp"))

    def test_parse_modules_filters_and_deduplicates(self) -> None:
        good, bad = scaffold.parse_modules("order, example,order,,product")
        self.assertEqual(good, ["order", "product"])
        self.assertEqual(bad, [])

        good, bad = scaffold.parse_modules("../secret,Order,class,product-item")
        self.assertEqual(good, [])
        self.assertEqual(bad, ["../secret", "Order", "class", "product-item"])

    def test_find_collisions_detects_runtime_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            templates.mkdir()
            (templates / "runtime.sh").write_text("export PROJECT_NAME=bad\n", encoding="utf-8")
            with mock.patch.object(scaffold, "TEMPLATES", templates):
                hits = scaffold.find_collisions({"PROJECT_NAME": "demo"})
        self.assertEqual(hits, ["runtime.sh:1  PROJECT_NAME"])

    def test_current_templates_have_no_collisions(self) -> None:
        ctx = scaffold.build_context(
            "demo-app", "com.example.demoapp", "0.2.0", 18080, 15173, 18081, "demo_app"
        )
        self.assertEqual(scaffold.find_collisions(ctx), [])

    def test_plan_keepfiles_does_not_add_to_nonempty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            existing = out / "docs" / "adr"
            existing.mkdir(parents=True)
            (existing / "decision.md").write_text("kept", encoding="utf-8")
            ctx = scaffold.build_context(
                "demo-app", "com.example.demoapp", "0.2.0", 8080, 5173, 8081, "demo_app"
            )
            keeps = scaffold.plan_keepfiles(out, ctx, [], [])
        self.assertNotIn(existing / ".gitkeep", keeps)


class ScaffoldGenerationTest(unittest.TestCase):
    @staticmethod
    def args(out: Path, **overrides: object) -> Namespace:
        values = {
            "name": "demo-app",
            "package": "com.example.demoapp",
            "out": str(out),
            "version": "0.2.0",
            "backend_port": 18080,
            "frontend_port": 15173,
            "web_port": 18081,
            "db_name": "demo_app",
            "modules": "order,product",
            "with_deploy": False,
            "with_ops": False,
            "with_testing": False,
            "force": False,
            "dry_run": False,
        }
        values.update(overrides)
        return Namespace(**values)

    def test_dry_run_is_side_effect_free_and_matches_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            args = self.args(out, modules="")
            preview = io.StringIO()
            with contextlib.redirect_stdout(preview):
                self.assertEqual(scaffold.generate(self.args(out, dry_run=True, modules="")), 0)
            self.assertFalse(out.exists())

            output = preview.getvalue()
            block = output.split("==> dry-run：以下文件将被创建或覆盖（不落盘）\n", 1)[1]
            listed, count = block.split("\n    共 ", 1)
            planned = {line.strip() for line in listed.splitlines() if line.startswith("    ")}
            self.assertEqual(len(planned), int(count.split(" 个文件", 1)[0]))

            self.assertEqual(scaffold.generate(args), 0)
            actual = {
                path.relative_to(out).as_posix()
                for path in out.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual, planned)
            self.assertIn("backend/src/main/java/com/example/demoapp/DemoAppApplication.java", actual)
            self.assertIn("frontend/package.json", actual)
            self.assertIn("scripts/check-doc-links.sh", actual)

    def test_all_optional_switch_combinations_have_expected_representatives(self) -> None:
        for deploy, ops, testing in itertools.product((False, True), repeat=3):
            with self.subTest(deploy=deploy, ops=ops, testing=testing):
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "generated"
                    self.assertEqual(
                        scaffold.generate(
                            self.args(
                                out,
                                modules="",
                                with_deploy=deploy,
                                with_ops=ops,
                                with_testing=testing,
                            )
                        ),
                        0,
                    )
                    self.assertTrue((out / "docs/adr/README.md").is_file())
                    self.assertTrue((out / "backend/src/test/java/com/example/demoapp/module/example/service/ExampleServiceTest.java").is_file())
                    self.assertEqual((out / "deploy/README.md").exists(), deploy)
                    self.assertEqual((out / "docs/operations/内存策略.md").exists(), ops)
                    self.assertEqual((out / "docs/testing/README.md").exists(), testing)

    def test_custom_values_render_and_shell_files_are_utf8_lf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            self.assertEqual(
                scaffold.generate(
                    self.args(
                        out,
                        name="reading-room",
                        package="org.example.readingroom",
                        version="1.4.0",
                        backend_port=19080,
                        frontend_port=16173,
                        web_port=19081,
                        db_name="reading_room",
                        modules="catalog",
                        with_testing=True,
                    )
                ),
                0,
            )
            application = (out / "backend/src/main/java/org/example/readingroom/ReadingRoomApplication.java").read_text(encoding="utf-8")
            config = (out / "backend/src/main/resources/application.yml").read_text(encoding="utf-8")
            self.assertIn("package org.example.readingroom;", application)
            self.assertIn("19080", config)
            self.assertIn("reading_room", config)
            self.assertIn("${READINGROOM_JWT_SECRET:", config)
            self.assertNotIn(b"\r\n", (out / "scripts/check-doc-links.sh").read_bytes())

    def test_nonempty_directory_requires_force_and_force_keeps_user_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            out.mkdir()
            user_file = out / "keep.txt"
            user_file.write_text("user content", encoding="utf-8")
            args = self.args(out)
            self.assertEqual(scaffold.generate(args), 2)
            self.assertFalse((out / "README.md").exists())

            self.assertEqual(scaffold.generate(self.args(out, force=True)), 0)
            self.assertEqual(user_file.read_text(encoding="utf-8"), "user content")

    def test_file_output_path_is_rejected_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "not-a-directory"
            out.write_text("occupied", encoding="utf-8")
            self.assertEqual(scaffold.generate(self.args(out)), 2)

    def test_invalid_cli_argument_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            with self.assertRaises(SystemExit) as error:
                scaffold.main(["--name", "demo-app", "--out", str(out), "--backend-port", "0"])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

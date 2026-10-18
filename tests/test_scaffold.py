from __future__ import annotations

import contextlib
import io
import itertools
import json
import subprocess
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
            "json": False,
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
            self.assertIn(".scaffold.json", actual)

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

                    integration_test = out / "backend/src/test/java/com/example/demoapp/module/example/ExampleApiIT.java"
                    self.assertTrue(integration_test.is_file())
                    integration_text = integration_test.read_text(encoding="utf-8")
                    self.assertIn('new MySQLContainer<>("mysql:8")', integration_text)
                    self.assertNotIn("${", integration_text)

                    ci_text = (out / ".github/workflows/ci.yml").read_text(encoding="utf-8")
                    self.assertIn("integration:", ci_text)
                    self.assertIn("mvn -B -ntp verify", ci_text)
                    self.assertIn("target/failsafe-reports/TEST-*IT.xml", ci_text)

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


class DependabotTemplateTest(unittest.TestCase):
    TEMPLATE = ROOT / "templates" / "root" / ".github" / "dependabot.yml"

    @staticmethod
    def load(text: str) -> dict:
        # 文件头是给人看的注释，正文是 JSON 写法（JSON 也是合法 YAML）。
        body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        return json.loads(body)

    def test_template_is_parsable_and_covers_expected_ecosystems(self) -> None:
        text = self.TEMPLATE.read_text(encoding="utf-8")
        plan = self.load(text)

        self.assertEqual(plan["version"], 2)
        self.assertEqual(
            [(u["package-ecosystem"], u["directory"]) for u in plan["updates"]],
            [("maven", "/backend"), ("npm", "/frontend"), ("github-actions", "/")],
        )
        for update in plan["updates"]:
            self.assertEqual(update["schedule"]["interval"], "weekly")
            self.assertLessEqual(update["open-pull-requests-limit"], 3)
            self.assertTrue(update["groups"])
            for group in update["groups"].values():
                self.assertNotIn("major", group.get("update-types", []))

    def test_template_has_no_credentials_private_registry_or_auto_merge(self) -> None:
        text = self.TEMPLATE.read_text(encoding="utf-8")
        plan = self.load(text)

        def keys(value: object):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertNotIn("registries", plan)
        self.assertNotIn("auto-merge", json.dumps(plan))
        self.assertFalse({"token", "password", "username"} & set(keys(plan)))
        for marker in ("git@", "http://"):
            self.assertNotIn(marker, text.lower())

    def test_every_switch_combination_ships_dependabot_outside_workflows(self) -> None:
        for deploy, ops, testing in itertools.product((False, True), repeat=3):
            with self.subTest(deploy=deploy, ops=ops, testing=testing):
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "generated"
                    self.assertEqual(
                        scaffold.generate(
                            ScaffoldGenerationTest.args(
                                out, modules="", with_deploy=deploy,
                                with_ops=ops, with_testing=testing,
                            )
                        ),
                        0,
                    )
                    config = out / ".github" / "dependabot.yml"
                    self.assertTrue(config.is_file())
                    self.assertFalse((out / ".github/workflows/dependabot.yml").exists())
                    rendered = config.read_text(encoding="utf-8")
                    self.assertEqual(self.load(rendered), self.load(self.TEMPLATE.read_text(encoding="utf-8")))
                    self.assertNotIn("${", rendered)


FIXED_SOURCE = {"commit": "a" * 40, "dirty": False, "status": "git"}


class ScaffoldRecordTest(unittest.TestCase):
    def generate(self, out: Path, **overrides: object) -> int:
        with mock.patch.object(scaffold, "detect_generator_source", return_value=dict(FIXED_SOURCE)):
            return scaffold.generate(ScaffoldGenerationTest.args(out, **overrides))

    def read(self, out: Path) -> dict:
        return json.loads((out / ".scaffold.json").read_text(encoding="utf-8"))

    def test_record_has_parsed_values_and_no_private_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            self.assertEqual(
                self.generate(
                    out,
                    name="reading-room", package="org.example.readingroom",
                    version="1.2.0", backend_port=19080, frontend_port=16173,
                    web_port=19081, db_name="reading_room",
                    modules="catalog,example,catalog", with_testing=True,
                ),
                0,
            )
            text = (out / ".scaffold.json").read_text(encoding="utf-8")
            raw = (out / ".scaffold.json").read_bytes()
            record = self.read(out)

        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["generator"]["name"], "project-scaffold")
        self.assertEqual(record["generator"]["source"], FIXED_SOURCE)
        project = record["project"]
        self.assertEqual(project["name"], "reading-room")
        self.assertEqual(project["package"], "org.example.readingroom")
        self.assertEqual(project["initial_version"], "1.2.0")
        self.assertEqual(project["database"], "reading_room")
        self.assertEqual(project["ports"], {"backend": 19080, "frontend": 16173, "web": 19081})
        self.assertEqual(project["modules"], ["catalog"])
        self.assertEqual(project["switches"], {"deploy": False, "ops": False, "testing": True})

        for forbidden in (str(out.resolve()), "generated_at", '"force"', "dry_run", "argv", "environ"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(text.endswith("\n"))

    def test_json_preview_record_matches_written_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            preview = io.StringIO()
            with mock.patch.object(scaffold, "detect_generator_source", return_value=dict(FIXED_SOURCE)):
                with contextlib.redirect_stdout(preview):
                    self.assertEqual(
                        scaffold.generate(
                            ScaffoldGenerationTest.args(out, dry_run=True, json=True,
                                                        modules="order", with_testing=True)
                        ),
                        0,
                    )
            plan = json.loads(preview.getvalue())
            self.assertFalse(out.exists())
            self.assertIn(".scaffold.json", plan["files"])
            self.assertEqual(plan["files"].count(".scaffold.json"), 1)
            self.assertEqual(plan["file_count"], len(plan["files"]))
            self.assertEqual(plan["scaffold_record"]["path"], ".scaffold.json")

            self.assertEqual(
                self.generate(out, modules="order", with_testing=True),
                0,
            )
            self.assertEqual(self.read(out), plan["scaffold_record"]["content"])

    def test_text_dry_run_shows_source_and_record_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            preview = io.StringIO()
            with mock.patch.object(scaffold, "detect_generator_source", return_value=dict(FIXED_SOURCE)):
                with contextlib.redirect_stdout(preview):
                    self.assertEqual(
                        scaffold.generate(ScaffoldGenerationTest.args(out, dry_run=True)), 0
                    )
            text = preview.getvalue()
        self.assertIn("脚手架来源：aaaaaaa", text)
        self.assertIn(".scaffold.json", text)
        self.assertFalse(out.exists())

    def test_unknown_source_is_recorded_as_unknown(self) -> None:
        unknown = {"commit": None, "dirty": None, "status": "unknown"}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            with mock.patch.object(scaffold, "detect_generator_source", return_value=dict(unknown)):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        scaffold.generate(ScaffoldGenerationTest.args(out)), 0
                    )
            record = self.read(out)
        self.assertEqual(record["generator"]["source"], unknown)

    def test_force_updates_record_and_keeps_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            self.assertEqual(self.generate(out, version="0.1.0"), 0)
            keep = out / "keep.txt"
            keep.write_text("user content", encoding="utf-8")

            self.assertEqual(self.generate(out, version="0.2.0", force=True), 0)
            self.assertEqual(self.read(out)["project"]["initial_version"], "0.2.0")
            self.assertEqual(keep.read_text(encoding="utf-8"), "user content")

    def test_invalid_existing_record_blocks_even_with_force(self) -> None:
        for content in (
            "{broken",
            '{"schema_version": 2, "generator": {"name": "project-scaffold"}}',
            '{"schema_version": 1, "generator": {"name": "other"}}',
        ):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "generated"
                    out.mkdir()
                    record = out / ".scaffold.json"
                    record.write_text(content, encoding="utf-8")
                    self.assertEqual(self.generate(out, force=True), 2)
                    self.assertEqual(record.read_text(encoding="utf-8"), content)
                    self.assertFalse((out / "README.md").exists())

    def test_record_path_occupied_by_directory_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            (out / ".scaffold.json").mkdir(parents=True)
            self.assertEqual(self.generate(out, force=True), 2)
            self.assertFalse((out / "README.md").exists())

    def test_template_write_failure_does_not_publish_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            with mock.patch.object(scaffold, "write_text", side_effect=OSError("disk full")):
                self.assertEqual(self.generate(out), 2)
            self.assertFalse((out / ".scaffold.json").exists())

    def test_record_write_failure_keeps_old_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            self.assertEqual(self.generate(out, version="0.1.0"), 0)
            before = (out / ".scaffold.json").read_text(encoding="utf-8")

            with mock.patch.object(scaffold, "write_scaffold_record", side_effect=OSError("disk full")):
                self.assertEqual(self.generate(out, version="0.2.0", force=True), 2)
            self.assertEqual((out / ".scaffold.json").read_text(encoding="utf-8"), before)

    def test_bad_template_encoding_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            (templates / "root").mkdir(parents=True)
            (templates / "root" / "bad.txt").write_bytes(b"\xff\xfe\x00")
            out = Path(tmp) / "generated"
            with mock.patch.object(scaffold, "TEMPLATES", templates), \
                    mock.patch.object(scaffold, "DIR_PLAN", [("root", ".", None)]):
                self.assertEqual(self.generate(out), 2)
            self.assertFalse(out.exists())

    def test_missing_template_directory_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            templates = Path(tmp) / "templates"
            templates.mkdir()
            out = Path(tmp) / "generated"
            with mock.patch.object(scaffold, "TEMPLATES", templates), \
                    mock.patch.object(scaffold, "DIR_PLAN", [("root", ".", None)]):
                self.assertEqual(self.generate(out), 2)
            self.assertFalse(out.exists())


class GeneratorSourceTest(unittest.TestCase):
    @staticmethod
    def git(*args: str, cwd: Path) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    def make_repo(self, tmp: str) -> Path:
        repo = Path(tmp) / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "templates").mkdir()
        (repo / "scripts" / "scaffold.py").write_text("# generator\n", encoding="utf-8")
        (repo / "templates" / "a.txt").write_text("a\n", encoding="utf-8")
        (repo / "README.md").write_text("readme\n", encoding="utf-8")
        self.git("init", "-q", "-b", "main", cwd=repo)
        self.git("config", "user.email", "t@example.com", cwd=repo)
        self.git("config", "user.name", "t", cwd=repo)
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", "init", cwd=repo)
        return repo

    def test_clean_repository_reports_git_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            source = scaffold.detect_generator_source(repo)
            expected = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                capture_output=True, text=True, encoding="utf-8",
            ).stdout.strip()
        self.assertEqual(source, {"commit": expected, "dirty": False, "status": "git"})

    def test_dirty_only_tracks_generator_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            self.assertFalse(scaffold.detect_generator_source(repo)["dirty"])

            (repo / "templates" / "new.txt").write_text("new\n", encoding="utf-8")
            self.assertTrue(scaffold.detect_generator_source(repo)["dirty"])

            (repo / "templates" / "new.txt").unlink()
            (repo / "scripts" / "scaffold.py").write_text("# changed\n", encoding="utf-8")
            self.assertTrue(scaffold.detect_generator_source(repo)["dirty"])

    def test_non_repository_and_nested_directory_are_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain"
            plain.mkdir()
            self.assertEqual(scaffold.detect_generator_source(plain)["status"], "unknown")

            repo = self.make_repo(tmp)
            nested = repo / "sub"
            nested.mkdir()
            self.assertEqual(scaffold.detect_generator_source(nested)["status"], "unknown")

    def test_repository_without_commit_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "empty"
            repo.mkdir()
            self.git("init", "-q", "-b", "main", cwd=repo)
            source = scaffold.detect_generator_source(repo)
        self.assertEqual(source, {"commit": None, "dirty": None, "status": "unknown"})


class ScaffoldJsonTest(unittest.TestCase):
    def run_json(self, out: Path, *extra: str) -> dict:
        argv = [
            "--name", "demo-app",
            "--package", "com.example.demoapp",
            "--out", str(out),
            "--dry-run", "--json",
            *extra,
        ]
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            self.assertEqual(scaffold.main(argv), 0)
        return json.loads(captured.getvalue())

    def test_json_dry_run_has_stable_shape_and_matches_real_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            plan = self.run_json(out, "--modules", "order", "--with-testing")

            self.assertEqual(plan["project"], "demo-app")
            self.assertEqual(plan["package"], "com.example.demoapp")
            self.assertEqual(Path(plan["out"]), out.resolve())
            self.assertEqual(plan["version"], "0.1.0")
            self.assertEqual(plan["database"], "demo_app")
            self.assertEqual(plan["ports"], {"backend": 8080, "frontend": 5173, "web": 8081})
            self.assertEqual(plan["modules"], ["order"])
            self.assertEqual(plan["switches"], {"deploy": False, "ops": False, "testing": True})
            self.assertTrue(plan["dry_run"])
            self.assertEqual(plan["target"]["state"], "missing")
            self.assertFalse(plan["target"]["would_refuse"])
            self.assertEqual(plan["file_count"], len(plan["files"]))
            self.assertEqual(len(plan["files"]), len(set(plan["files"])))
            self.assertFalse(any(f.startswith(("/", "\\")) for f in plan["files"]))
            self.assertFalse(out.exists(), "dry-run 不能创建输出目录")

            args = Namespace(
                name="demo-app", package="com.example.demoapp", out=str(out),
                version="0.1.0", backend_port=8080, frontend_port=5173, web_port=8081,
                db_name="demo_app", modules="order", with_deploy=False,
                with_ops=False, with_testing=True, force=False, dry_run=False, json=False,
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scaffold.generate(args), 0)
            actual = {
                path.relative_to(out).as_posix()
                for path in out.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual, set(plan["files"]))

    def test_json_target_state_reports_refusal_for_nonempty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            out.mkdir()
            (out / "keep.txt").write_text("user content", encoding="utf-8")

            plan = self.run_json(out)
            self.assertEqual(plan["target"]["state"], "non_empty")
            self.assertTrue(plan["target"]["would_refuse"])

            plan = self.run_json(out, "--force")
            self.assertFalse(plan["target"]["would_refuse"])
            self.assertTrue(plan["force"])

    def test_json_requires_dry_run_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    scaffold.main(["--name", "demo-app", "--out", str(out), "--json"])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(out.exists())

    def test_json_cli_subprocess_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            # 不设 PYTHONIOENCODING：JSON 模式内部固定 UTF-8，中文路径也要能按 UTF-8 解析。
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "scaffold.py"),
                 "--name", "demo-app", "--out", str(out), "--dry-run", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["file_count"], len(plan["files"]))
            self.assertIn("docs/design/设计skill清单.md", plan["files"])
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

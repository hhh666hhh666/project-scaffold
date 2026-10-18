from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_consistency as cc

# 检查器只读这些文件；测试把它们复制进临时根目录，再故意改坏其中一处。
FIXTURE_FILES = (
    "templates/backend/pom.xml",
    "templates/backend/Dockerfile",
    "templates/frontend/package.json",
    "templates/frontend/Dockerfile",
    "templates/ci/ci.yml",
    "templates/docker/docker-compose.dev.yml",
    "templates/deploy/docker-compose.prod.yml",
    "templates/deploy/.github/workflows/release.yml",
    "templates/backend/src/test/java/${PACKAGE_PATH}/support/IntegrationTestBase.java",
    ".github/workflows/full-build.yml",
    "references/TECH-STACK.md",
    "references/SKILL-SOURCES.json",
    "README.md",
    "references/POST-SCAFFOLD.md",
    "templates/rules/design-skills.md",
    "templates/docs/design/设计skill清单.md",
)


def clone_root(tmp: str) -> Path:
    root = Path(tmp)
    for rel in FIXTURE_FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    return root


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"fixture 里找不到要替换的内容：{old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def rewrite_block(path: Path, marker: str, transform) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    head, rest = text.split(start, 1)
    block, tail = rest.split(end, 1)
    path.write_text(head + start + transform(block) + end + tail, encoding="utf-8")


def drop_table_row(path: Path, marker: str, needle: str) -> None:
    def transform(block: str) -> str:
        kept = [line for line in block.splitlines(keepends=True) if needle not in line]
        if len(kept) == len(block.splitlines(keepends=True)):
            raise AssertionError(f"fixture 的表格里找不到包含 {needle!r} 的行")
        return "".join(kept)

    rewrite_block(path, marker, transform)


class ParserTest(unittest.TestCase):
    def test_pom_versions_reads_parent_and_properties(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent><groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId><version>9.9.9</version></parent>
  <properties>
    <java.version>42</java.version>
    <jjwt.version>1.2.3</jjwt.version>
  </properties>
</project>"""
        values = cc.pom_versions(xml)
        self.assertEqual(values["spring-boot"], "9.9.9")
        self.assertEqual(values["jdk"], "42")
        self.assertEqual(values["jjwt"], "1.2.3")
        self.assertEqual(values["springdoc"], "")

    def test_cell_text_prefers_backtick_and_accepts_bold(self) -> None:
        self.assertEqual(cc.cell_text("`grill-with-docs`（转调）"), "grill-with-docs")
        self.assertEqual(cc.cell_text("`shadcn-vue`（官方）"), "shadcn-vue")
        self.assertEqual(cc.cell_text("**impeccable**"), "impeccable")
        self.assertEqual(cc.cell_text("定方向 / 重设计"), "")

    def test_cell_url_takes_first_markdown_link(self) -> None:
        self.assertEqual(
            cc.cell_url("[x/y](https://github.com/x/y)（MIT）"),
            "https://github.com/x/y",
        )
        self.assertEqual(cc.cell_url("没有链接"), "")

    def test_marked_table_requires_exactly_one_marker_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "doc.md"
            path.write_text(
                "<!-- consistency:versions:start -->\n"
                "| 标识 | 版本 |\n|---|---|\n| `a` | `1` |\n"
                "<!-- consistency:versions:end -->\n",
                encoding="utf-8",
            )
            header, rows = cc.marked_table(cc.Checker(root), "doc.md", cc.VERSIONS_MARKER)
            self.assertEqual(header, ["标识", "版本"])
            self.assertEqual(rows, [["`a`", "`1`"]])

            path.write_text(path.read_text(encoding="utf-8") * 2, encoding="utf-8")
            checker = cc.Checker(root)
            self.assertIsNone(cc.marked_table(checker, "doc.md", cc.VERSIONS_MARKER))
            self.assertTrue(any("应出现 1 次" in p for p in checker.problems))


class VersionsTest(unittest.TestCase):
    def test_real_repository_versions_match_templates(self) -> None:
        self.assertEqual(cc.check_versions(ROOT), [])

    def test_stale_documented_version_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/TECH-STACK.md", "`3.5.16`", "`3.5.15`")
            problems = cc.check_versions(root)
        self.assertTrue(any("spring-boot" in p and "3.5.15" in p and "3.5.16" in p for p in problems), problems)

    def test_pom_change_without_doc_update_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/backend/pom.xml", "<jjwt.version>0.12.7</jjwt.version>",
                 "<jjwt.version>0.13.0</jjwt.version>")
            problems = cc.check_versions(root)
        self.assertTrue(any("jjwt" in p and "0.13.0" in p for p in problems), problems)

    def test_frontend_range_change_without_doc_update_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/frontend/package.json", '"vue": "^3.5.44"', '"vue": "^3.6.0"')
            problems = cc.check_versions(root)
        self.assertTrue(any("vue" in p and "^3.6.0" in p for p in problems), problems)

    def test_tailwind_plugin_must_match_tailwind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/frontend/package.json", '"@tailwindcss/vite": "^4.3.3"',
                 '"@tailwindcss/vite": "^4.4.0"')
            problems = cc.check_versions(root)
        self.assertTrue(any("@tailwindcss/vite" in p and "同版本发布" in p for p in problems), problems)

    def test_stale_jdk_in_generated_ci_workflow_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/ci/ci.yml", "java-version: '21'", "java-version: '17'")
            problems = cc.check_versions(root)
        self.assertTrue(any("templates/ci/ci.yml" in p and "jdk" in p for p in problems), problems)

    def test_stale_node_in_full_build_workflow_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / ".github/workflows/full-build.yml", "node-version: 22", "node-version: 20")
            problems = cc.check_versions(root)
        self.assertTrue(
            any(".github/workflows/full-build.yml" in p and "node" in p for p in problems), problems
        )

    def test_stale_nginx_in_frontend_dockerfile_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/frontend/Dockerfile", "FROM nginx:1.30-alpine", "FROM nginx:1.31-alpine")
            problems = cc.check_versions(root)
        self.assertTrue(any("nginx" in p and "1.31" in p for p in problems), problems)

    def test_missing_nginx_version_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "references/TECH-STACK.md", cc.VERSIONS_MARKER, "`nginx`")
            problems = cc.check_versions(root)
        self.assertTrue(any("版本表缺少登记项：nginx" in p for p in problems), problems)

    def test_every_mysql_image_occurrence_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = root / "templates/deploy/.github/workflows/release.yml"
            text = path.read_text(encoding="utf-8")
            # release.yml 里 mysql:8 出现两处；只改第二处，第一处仍是 8。
            self.assertGreaterEqual(text.count("mysql:8"), 2)
            path.write_text(text.replace(
                "docker run --rm --network host -i mysql:8",
                "docker run --rm --network host -i mysql:9",
            ), encoding="utf-8")
            problems = cc.check_versions(root)
        self.assertTrue(any("release.yml" in p and "mysql" in p and "9" in p for p in problems), problems)

    def test_missing_mysql_version_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "references/TECH-STACK.md", cc.VERSIONS_MARKER, "`mysql`")
            problems = cc.check_versions(root)
        self.assertTrue(any("版本表缺少登记项：mysql" in p for p in problems), problems)

    def test_stale_pinia_in_generated_frontend_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/frontend/package.json", '"pinia": "^3.0.4"', '"pinia": "^4.0.0"')
            problems = cc.check_versions(root)
        self.assertTrue(any("pinia" in p and "^4.0.0" in p for p in problems), problems)

    def test_missing_vue_test_utils_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "references/TECH-STACK.md", cc.VERSIONS_MARKER, "`vue-test-utils`")
            problems = cc.check_versions(root)
        self.assertTrue(any("版本表缺少登记项：vue-test-utils" in p for p in problems), problems)

    def test_coverage_plugin_must_match_vitest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/frontend/package.json", '"@vitest/coverage-v8": "^3.2.7"',
                 '"@vitest/coverage-v8": "^3.1.0"')
            problems = cc.check_versions(root)
        self.assertTrue(any("@vitest/coverage-v8" in p and "同版本线发布" in p for p in problems), problems)

    def test_missing_vue_router_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "references/TECH-STACK.md", cc.VERSIONS_MARKER, "`vue-router`")
            problems = cc.check_versions(root)
        self.assertTrue(any("版本表缺少登记项：vue-router" in p for p in problems), problems)

    def test_missing_version_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "references/TECH-STACK.md", cc.VERSIONS_MARKER, "`springdoc`")
            problems = cc.check_versions(root)
        self.assertTrue(any("版本表缺少登记项：springdoc" in p for p in problems), problems)

    def test_broken_pom_is_reported_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "templates/backend/pom.xml", "</project>", "</projects>")
            problems = cc.check_versions(root)
        self.assertTrue(any("XML 解析失败" in p for p in problems), problems)


class SkillsTest(unittest.TestCase):
    def test_real_repository_skill_tables_match_registry(self) -> None:
        self.assertEqual(cc.check_skills(ROOT), [])

    def test_missing_skill_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "README.md", cc.SOURCE_SKILLS_MARKER, "`ui-ux-pro-max`")
            problems = cc.check_skills(root)
        self.assertTrue(any("来源表缺少 skill：ui-ux-pro-max" in p for p in problems), problems)

    def test_unknown_skill_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            rewrite_block(
                root / "README.md",
                cc.SOURCE_SKILLS_MARKER,
                lambda block: block.rstrip("\n") + "\n| | `unknown-skill` | [x/y](https://github.com/x/y) |\n",
            )
            problems = cc.check_skills(root)
        self.assertTrue(any("未登记的 skill：unknown-skill" in p for p in problems), problems)

    def test_wrong_repository_url_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(
                root / "references/POST-SCAFFOLD.md",
                "[pbakaus/impeccable](https://github.com/pbakaus/impeccable)",
                "[pbakaus/impeccable](https://github.com/someone/impeccable)",
            )
            problems = cc.check_skills(root)
        self.assertTrue(any("impeccable" in p and "someone/impeccable" in p for p in problems), problems)

    def test_duplicate_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            drop_table_row(root / "templates/rules/design-skills.md", cc.DESIGN_SKILLS_MARKER, "`ui-ux-pro-max`")
            rewrite_block(
                root / "templates/rules/design-skills.md", cc.DESIGN_SKILLS_MARKER,
                lambda block: block.replace(
                    "| 用 shadcn-vue 组件（`add` / `search` / preset） | `shadcn-vue`（官方） | ⚠️ `user-invocable: false`，**只能 AI 自己用，@ 不到** |",
                    "| 重复 | `shadcn-vue` | 重复行 |\n"
                    "| 又是 shadcn | `shadcn-vue` | 重复行 |",
                ),
            )
            problems = cc.check_skills(root)
        self.assertTrue(any("设计清单缺少 skill：ui-ux-pro-max" in p for p in problems), problems)
        self.assertTrue(any("出现了不止一次" in p for p in problems), problems)

    def test_reordered_design_table_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = root / "templates/rules/design-skills.md"

            def reverse_rows(block: str) -> str:
                lines = block.splitlines(keepends=True)
                table = [i for i, line in enumerate(lines) if line.strip().startswith("|")]
                head, body = lines[: table[1] + 1], lines[table[1] + 1:]
                return "".join(head + list(reversed(body)))

            rewrite_block(path, cc.DESIGN_SKILLS_MARKER, reverse_rows)
            problems = cc.check_skills(root)
        self.assertEqual(problems, [])

    def test_missing_marker_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "README.md", "<!-- consistency:source-skills:end -->", "")
            problems = cc.check_skills(root)
        self.assertTrue(any("应出现 1 次" in p for p in problems), problems)

    def test_broken_table_separator_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(
                root / "templates/docs/design/设计skill清单.md",
                "| # | Skill | 角色 | 安装完整性 | 舍弃了什么 | 舍弃原因 | 什么时候用 |\n"
                "|---|---|---|---|---|---|---|",
                "| # | Skill | 角色 | 安装完整性 | 舍弃了什么 | 舍弃原因 | 什么时候用 |",
            )
            problems = cc.check_skills(root)
        self.assertTrue(any("分隔行" in p for p in problems), problems)


class RegistryTest(unittest.TestCase):
    def test_real_registry_is_valid(self) -> None:
        self.assertEqual(cc.registry_problems(), [])

    def test_group_member_must_exist(self) -> None:
        with mock.patch.dict(cc.fetch_skills.GROUPS, {"design": ["impeccable", "ghost"]}):
            problems = cc.registry_problems()
        self.assertTrue(any("成员 ghost" in p for p in problems), problems)

    def test_dependency_cycle_is_reported(self) -> None:
        with mock.patch.dict(
            cc.fetch_skills.SKILLS,
            {"a": ("https://github.com/x/y", "skills/a"), "b": ("https://github.com/x/y", "skills/b")},
        ), mock.patch.dict(cc.fetch_skills.DEPENDS, {"a": ["b"], "b": ["a"]}):
            problems = cc.registry_problems()
        self.assertTrue(any("依赖环" in p for p in problems), problems)


class SourcesCheckTest(unittest.TestCase):
    def lock_path(self, root: Path) -> Path:
        return root / "references" / "SKILL-SOURCES.json"

    def test_short_sha_in_lock_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = self.lock_path(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            first = next(iter(data["repositories"]))
            data["repositories"][first]["commit"] = "abc1234"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

            problems = cc.check_skills(root)
        self.assertTrue(any("40 位" in p for p in problems), problems)

    def test_missing_repository_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = self.lock_path(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["repositories"].pop("https://github.com/mattpocock/skills")
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

            problems = cc.check_skills(root)
        self.assertTrue(any("缺少仓库" in p for p in problems), problems)

    def test_duplicate_json_key_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = self.lock_path(root)
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,', 1),
                            encoding="utf-8")

            problems = cc.check_skills(root)
        self.assertTrue(any("锁定清单解析失败" in p for p in problems), problems)


class CliTest(unittest.TestCase):
    def test_cli_passes_on_real_repository(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cc.main([]), 0)
        text = output.getvalue()
        self.assertIn("依赖版本", text)
        self.assertIn("配套 skill 清单", text)
        self.assertIn("架构图与源文件", text)

    def test_cli_reports_failure_and_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/TECH-STACK.md", "`0.12.7`", "`0.11.0`")
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(cc, "ROOT", root):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(cc.main(["--only", "versions"]), 1)
        self.assertIn("jjwt", err.getvalue())
        self.assertIn("发现 1 处不一致", err.getvalue())

    def test_cli_only_skills_skips_versions(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cc.main(["--only", "skills"]), 0)
        self.assertNotIn("依赖版本", output.getvalue())

    def test_cli_only_diagrams_skips_other_groups(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cc.main(["--only", "diagrams"]), 0)
        text = output.getvalue()
        self.assertIn("架构图与源文件", text)
        self.assertNotIn("依赖版本", text)
        self.assertNotIn("配套 skill 清单", text)


if __name__ == "__main__":
    unittest.main()

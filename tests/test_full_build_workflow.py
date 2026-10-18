from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "full-build.yml"


def active_lines(text: str) -> list[str]:
    """去掉注释与空行：注释里可以自由提到 npm ci / Docker，不应被当成实际命令。"""
    return [
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class FullBuildWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.lines = active_lines(self.text)

    def test_triggers_are_weekly_manual_and_template_pull_requests(self) -> None:
        self.assertRegex(self.text, r"(?m)^on:\s*$")
        self.assertIn("cron: '17 2 * * 1'", self.text)
        self.assertRegex(self.text, r"(?m)^  workflow_dispatch:\s*$")
        self.assertRegex(self.text, r"(?m)^  pull_request:\s*$")

        # 模板或生成器改动最可能弄坏生成物，值得在 PR 上先拦一次；其余改动不触发。
        for path in ("'templates/**'", "'scripts/scaffold.py'", "'.github/workflows/full-build.yml'"):
            self.assertIn(path, self.text)

    def test_does_not_run_on_every_push(self) -> None:
        # 完整构建是分钟级任务，日常反馈交给 Selftest；这里只做定时、手动与模板 PR。
        self.assertNotRegex(self.text, r"(?m)^  push:\s*$")

    def test_permissions_are_read_only(self) -> None:
        self.assertRegex(self.text, r"(?m)^permissions:\s*$\n  contents: read\s*$")
        self.assertNotIn("write", self.text)
        self.assertNotIn("secrets.", self.text)

    def test_both_jobs_generate_an_all_switches_project(self) -> None:
        self.assertRegex(self.text, r"(?m)^  backend:\s*$")
        self.assertRegex(self.text, r"(?m)^  frontend:\s*$")
        self.assertEqual(self.text.count('--out "$RUNNER_TEMP/full-build"'), 2)
        self.assertEqual(self.text.count("--with-deploy --with-ops --with-testing"), 2)
        self.assertIn("python scripts/scaffold.py", self.text)

    def test_backend_runs_verify_and_checks_the_jar(self) -> None:
        runs = [line.strip() for line in self.lines if "mvn " in line]
        self.assertTrue(any(re.search(r"mvn -B -ntp verify$", line) for line in runs), runs)
        self.assertNotIn("mvn -B -ntp test", "\n".join(runs))
        self.assertIn("ls -l target/*.jar", self.text)
        self.assertIn("target/failsafe-reports/TEST-*IT.xml", self.text)
        self.assertIn("if: failure()", self.text)

    def test_frontend_installs_without_lockfile_then_typechecks_tests_and_builds(self) -> None:
        active = "\n".join(self.lines)
        self.assertIn("npm install --no-audit --no-fund", active)
        # 模板不带 package-lock.json，npm ci 会直接失败；这条约束必须显式守住。
        self.assertNotIn("npm ci", active)
        self.assertIn("npm run typecheck", active)
        self.assertIn("npm run test", active)
        self.assertIn("npm run build", active)
        # 顺序有意义：单测在构建之前，构建失败前的逻辑错误先由测试暴露。
        self.assertLess(active.index("npm run typecheck"), active.index("npm run test"))
        self.assertLess(active.index("npm run test"), active.index("npm run build"))
        self.assertIn("test -f dist/index.html", active)

    def test_workflow_does_not_touch_other_repositories_or_deploy(self) -> None:
        active = "\n".join(self.lines).lower()
        for marker in ("docker build", "ssh ", "git push", "gh repo create", "deploy.sh"):
            self.assertNotIn(marker, active)


if __name__ == "__main__":
    unittest.main()

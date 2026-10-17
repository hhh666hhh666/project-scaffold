from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_skills


class LocateTest(unittest.TestCase):
    def test_registered_path_wins(self) -> None:
        tree = {
            "skills/web-design-guidelines/SKILL.md",
            "other/web-design-guidelines/SKILL.md",
        }
        self.assertEqual(
            fetch_skills.locate(tree, "web-design-guidelines", "skills/web-design-guidelines"),
            "skills/web-design-guidelines",
        )

    def test_unique_moved_path_is_used(self) -> None:
        tree = {"new/place/grilling/SKILL.md"}
        self.assertEqual(fetch_skills.locate(tree, "grilling", "skills/productivity/grilling"), "new/place/grilling")

    def test_missing_or_ambiguous_path_fails(self) -> None:
        with self.assertRaises(LookupError):
            fetch_skills.locate(set(), "grilling", "skills/productivity/grilling")
        with self.assertRaises(LookupError):
            fetch_skills.locate(
                {"a/grilling/SKILL.md", "b/grilling/SKILL.md"},
                "grilling",
                "skills/productivity/grilling",
            )

    def test_tests_directory_is_not_a_fallback_candidate(self) -> None:
        with self.assertRaises(LookupError):
            fetch_skills.locate({"tests/grilling/SKILL.md"}, "grilling", "skills/productivity/grilling")


class FetchCheckTest(unittest.TestCase):
    def test_check_expands_alias_and_dependencies_without_network_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            output = io.StringIO()
            with mock.patch.object(fetch_skills.shutil, "which", side_effect=AssertionError("git lookup must not run")):
                with contextlib.redirect_stdout(output):
                    result = fetch_skills.main(["--dest", str(dest), "grill-with-docs", "design", "--check"])

            self.assertEqual(result, 0)
            text = output.getvalue()
            for name in ("grill-with-docs", "grilling", "domain-modeling", "impeccable", "ui-ux-pro-max"):
                self.assertIn(name, text)
            self.assertFalse(dest.exists())

    def test_check_recognizes_existing_skill_without_requiring_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            skill = dest / "grilling"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("local", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(fetch_skills.shutil, "which", side_effect=AssertionError("git lookup must not run")):
                with contextlib.redirect_stdout(output):
                    result = fetch_skills.main(["--dest", str(dest), "grilling", "--check"])

            self.assertEqual(result, 0)
            self.assertIn("已装", output.getvalue())
            self.assertNotIn("缺 1 个", output.getvalue())

    def test_explicit_flavor_wins_over_destination_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / ".claude" / "skills"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = fetch_skills.main(
                    ["--dest", str(dest), "--flavor", "agent", "impeccable", "--check"]
                )

            self.assertEqual(result, 0)
            self.assertIn(".agent/skills/impeccable", output.getvalue())
            self.assertNotIn(".claude/skills/impeccable", output.getvalue())

    def test_all_installed_short_circuits_before_git_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            for name in ("grill-with-docs", "grilling", "domain-modeling"):
                skill = dest / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("local", encoding="utf-8")
            with mock.patch.object(fetch_skills.shutil, "which", side_effect=AssertionError("git lookup must not run")):
                result = fetch_skills.main(["--dest", str(dest), "grill-with-docs"])
            self.assertEqual(result, 0)


class FetchInstallFlowTest(unittest.TestCase):
    def test_install_groups_skills_by_repository_and_does_not_overwrite_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            existing = dest / "grilling"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("keep me", encoding="utf-8")

            calls: list[tuple[str, ...]] = []

            def fake_git(*args: str, cwd: Path | None = None) -> str:
                calls.append(args)
                if args[:2] == ("clone", "--filter=blob:none"):
                    work = Path(args[-1])
                    (work / "skills/engineering/grill-with-docs").mkdir(parents=True)
                    (work / "skills/engineering/grill-with-docs/SKILL.md").write_text("wrapper", encoding="utf-8")
                    (work / "skills/productivity/grilling").mkdir(parents=True)
                    (work / "skills/productivity/grilling/SKILL.md").write_text("grill", encoding="utf-8")
                    (work / "skills/engineering/domain-modeling").mkdir(parents=True)
                    (work / "skills/engineering/domain-modeling/SKILL.md").write_text("domain", encoding="utf-8")
                    return ""
                if args[:2] == ("rev-parse", "--short"):
                    return "abc1234"
                if args[:3] == ("ls-tree", "-r", "--name-only"):
                    return (
                        "skills/engineering/grill-with-docs/SKILL.md\n"
                        "skills/productivity/grilling/SKILL.md\n"
                        "skills/engineering/domain-modeling/SKILL.md"
                    )
                return ""

            with mock.patch.object(fetch_skills, "git", side_effect=fake_git):
                result = fetch_skills.main(["--dest", str(dest), "grill-with-docs"])

            self.assertEqual(result, 0)
            self.assertEqual((dest / "grilling/SKILL.md").read_text(encoding="utf-8"), "keep me")
            self.assertEqual((dest / "grill-with-docs/SKILL.md").read_text(encoding="utf-8"), "wrapper")
            self.assertEqual(
                sum(1 for call in calls if call[:2] == ("clone", "--filter=blob:none")),
                1,
            )


if __name__ == "__main__":
    unittest.main()

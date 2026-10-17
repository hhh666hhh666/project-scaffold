from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_skills


def locked_commit() -> str:
    sources = fetch_skills.load_sources()
    return sources["repositories"][fetch_skills.MATT]["commit"]


class SourcesTest(unittest.TestCase):
    def test_real_sources_are_valid(self) -> None:
        sources = fetch_skills.load_sources()
        self.assertEqual(fetch_skills.source_problems(sources), [])

    def test_missing_repository_is_reported(self) -> None:
        skills = {"a": ("https://github.com/x/y", "skills/a")}
        sources = {"schema_version": 1, "repositories": {}}
        self.assertTrue(any("缺少仓库" in p for p in fetch_skills.source_problems(sources, skills)))

    def test_unknown_repository_is_reported(self) -> None:
        skills = {"a": ("https://github.com/x/y", "skills/a")}
        sources = {
            "schema_version": 1,
            "repositories": {
                "https://github.com/x/y": {"commit": "a" * 40, "branch": "main"},
                "https://github.com/x/z": {"commit": "b" * 40, "branch": "main"},
            },
        }
        self.assertTrue(any("未登记的仓库" in p for p in fetch_skills.source_problems(sources, skills)))

    def test_short_or_floating_commit_is_rejected(self) -> None:
        skills = {"a": ("https://github.com/x/y", "skills/a")}
        for bad in ("abc1234", "main", "A" * 40, "a" * 39):
            sources = {"schema_version": 1, "repositories": {
                "https://github.com/x/y": {"commit": bad, "branch": "main"}}}
            self.assertTrue(
                any("40 位" in p for p in fetch_skills.source_problems(sources, skills)),
                bad,
            )

    def test_branch_must_be_non_empty_and_single_token(self) -> None:
        skills = {"a": ("https://github.com/x/y", "skills/a")}
        for bad in ("", "main branch"):
            sources = {"schema_version": 1, "repositories": {
                "https://github.com/x/y": {"commit": "a" * 40, "branch": bad}}}
            self.assertTrue(
                any("branch" in p for p in fetch_skills.source_problems(sources, skills)),
                bad,
            )

    def test_duplicate_json_key_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            path.write_text(
                '{"schema_version": 1, "schema_version": 1, "repositories": {}}',
                encoding="utf-8",
            )
            with self.assertRaises(fetch_skills.SourceError):
                fetch_skills.load_sources(path)


class ExpandNamesTest(unittest.TestCase):
    def test_dependencies_are_recursive_and_deduplicated(self) -> None:
        with mock.patch.dict(fetch_skills.DEPENDS, {"a": ["b"], "b": ["c"]}, clear=True):
            self.assertEqual(fetch_skills.expand_names(["a", "b"]), ["a", "b", "c"])

    def test_cycle_is_rejected_before_network(self) -> None:
        with mock.patch.dict(fetch_skills.DEPENDS, {"a": ["b"], "b": ["a"]}, clear=True):
            with self.assertRaises(ValueError):
                fetch_skills.expand_names(["a"])


class LockedSourceTest(unittest.TestCase):
    def test_exact_registered_path_wins(self) -> None:
        tree = {"skills/a/SKILL.md", "other/a/SKILL.md"}
        self.assertEqual(fetch_skills.locked_source(tree, "a", "skills/a"), "skills/a")

    def test_missing_registered_path_fails_without_fallback(self) -> None:
        with self.assertRaises(LookupError):
            fetch_skills.locked_source({"new/place/a/SKILL.md"}, "a", "skills/a")
        with self.assertRaises(LookupError):
            fetch_skills.locked_source(set(), "a", "skills/a")


class SkillStateTest(unittest.TestCase):
    def test_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.assertEqual(fetch_skills.skill_state(dest, "missing"), "missing")

            complete = dest / "complete"
            complete.mkdir()
            (complete / "SKILL.md").write_text("x", encoding="utf-8")
            self.assertEqual(fetch_skills.skill_state(dest, "complete"), "installed")

            incomplete = dest / "incomplete"
            incomplete.mkdir()
            (incomplete / "README.md").write_text("x", encoding="utf-8")
            self.assertEqual(fetch_skills.skill_state(dest, "incomplete"), "incomplete")

            (dest / "file").write_text("x", encoding="utf-8")
            self.assertEqual(fetch_skills.skill_state(dest, "file"), "file")


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
            self.assertIn(locked_commit()[:7], text)
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
            self.assertIn("来源未知", output.getvalue())
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

    def test_check_and_outdated_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    fetch_skills.main(["--dest", tmp, "--check", "--outdated", "grilling"])
            self.assertEqual(error.exception.code, 2)


class FetchInstallFlowTest(unittest.TestCase):
    def fake_git(self, commit: str, calls: list[tuple[str, ...]]):
        def fake(*args: str, cwd: Path | None = None) -> str:
            calls.append(args)
            if args[:2] == ("fetch", "-q"):
                work = cwd
                (work / "skills/engineering/grill-with-docs").mkdir(parents=True)
                (work / "skills/engineering/grill-with-docs/SKILL.md").write_text("wrapper", encoding="utf-8")
                (work / "skills/productivity/grilling").mkdir(parents=True)
                (work / "skills/productivity/grilling/SKILL.md").write_text("grill", encoding="utf-8")
                (work / "skills/engineering/domain-modeling").mkdir(parents=True)
                (work / "skills/engineering/domain-modeling/SKILL.md").write_text("domain", encoding="utf-8")
                return ""
            if args[:2] == ("rev-parse", "FETCH_HEAD") or args[:2] == ("rev-parse", "HEAD"):
                return commit
            if args[:3] == ("ls-tree", "-r", "--name-only"):
                return (
                    "skills/engineering/grill-with-docs/SKILL.md\n"
                    "skills/productivity/grilling/SKILL.md\n"
                    "skills/engineering/domain-modeling/SKILL.md"
                )
            return ""
        return fake

    def test_install_groups_by_repository_uses_locked_sha_and_does_not_overwrite(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            existing = dest / "grilling"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("keep me", encoding="utf-8")

            calls: list[tuple[str, ...]] = []
            with mock.patch.object(fetch_skills, "git", side_effect=self.fake_git(commit, calls)):
                result = fetch_skills.main(["--dest", str(dest), "grill-with-docs"])

            self.assertEqual(result, 0)
            self.assertEqual((dest / "grilling/SKILL.md").read_text(encoding="utf-8"), "keep me")
            self.assertEqual((dest / "grill-with-docs/SKILL.md").read_text(encoding="utf-8"), "wrapper")
            self.assertFalse((dest / "grilling/.fetched.json").exists())
            fetches = [call for call in calls if call[:2] == ("fetch", "-q")]
            self.assertEqual(len(fetches), 1)
            self.assertEqual(fetches[0][-1], commit)

            metadata = json.loads((dest / "grill-with-docs/.fetched.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], 1)
            self.assertEqual(metadata["skill"], "grill-with-docs")
            self.assertEqual(metadata["repository"], fetch_skills.MATT)
            self.assertEqual(metadata["commit"], commit)
            self.assertEqual(metadata["source_path"], "skills/engineering/grill-with-docs")
            self.assertEqual(metadata["flavor"], "agent")
            self.assertEqual([item["path"] for item in metadata["files"]], ["SKILL.md"])

    def test_fetch_failure_reports_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"

            def failing(*args: str, cwd: Path | None = None) -> str:
                raise fetch_skills.subprocess.CalledProcessError(1, "git", stderr="not found")

            with mock.patch.object(fetch_skills, "git", side_effect=failing):
                result = fetch_skills.main(["--dest", str(dest), "grilling"])
            self.assertEqual(result, 1)
            self.assertFalse((dest / "grilling").exists())

    def test_partial_failure_keeps_completed_install(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"

            def partial(*args: str, cwd: Path | None = None) -> str:
                repo_by_work.setdefault(cwd, "")
                if args[:2] == ("remote", "add"):
                    repo_by_work[cwd] = args[3]
                    return ""
                if args[:2] == ("fetch", "-q"):
                    if "make-interfaces-feel-better" in repo_by_work[cwd]:
                        raise fetch_skills.subprocess.CalledProcessError(1, "git", stderr="boom")
                    src = cwd / "skills/productivity/grilling"
                    src.mkdir(parents=True)
                    (src / "SKILL.md").write_text("grill", encoding="utf-8")
                    return ""
                if args[:2] in (("rev-parse", "FETCH_HEAD"), ("rev-parse", "HEAD")):
                    return commit
                if args[:3] == ("ls-tree", "-r", "--name-only"):
                    return "skills/productivity/grilling/SKILL.md"
                return ""

            repo_by_work: dict[Path | None, str] = {}
            with mock.patch.object(fetch_skills, "git", side_effect=partial):
                result = fetch_skills.main(["--dest", str(dest), "grilling", "make-interfaces-feel-better"])

            self.assertEqual(result, 1)
            self.assertTrue((dest / "grilling/SKILL.md").is_file())
            self.assertTrue((dest / "grilling/.fetched.json").is_file())
            self.assertFalse((dest / "make-interfaces-feel-better").exists())

    def test_occupied_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            occupied = dest / "grilling"
            occupied.mkdir(parents=True)
            (occupied / "keep.txt").write_text("keep", encoding="utf-8")

            with mock.patch.object(fetch_skills.shutil, "which", side_effect=AssertionError("must not fetch")):
                result = fetch_skills.main(["--dest", str(dest), "grilling"])
            self.assertEqual(result, 1)
            self.assertEqual((occupied / "keep.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse((occupied / ".fetched.json").exists())


class MetadataTest(unittest.TestCase):
    def install(self, dest: Path, name: str = "grilling") -> dict:
        work = dest.parent / "work"
        src = work / "skills/productivity/grilling"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("original", encoding="utf-8")
        (src / "extra.txt").write_text("extra", encoding="utf-8")
        commit = locked_commit()
        fetch_skills.install_one(dest, name, fetch_skills.MATT, commit, "agent",
                                 "skills/productivity/grilling", work)
        return json.loads((dest / name / ".fetched.json").read_text(encoding="utf-8"))

    def test_metadata_round_trip_and_original_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            dest.mkdir()
            meta = self.install(dest)
            read, problems = fetch_skills.read_metadata(dest / "grilling", "grilling")
            self.assertEqual(problems, [])
            self.assertEqual(read, meta)
            self.assertEqual(fetch_skills.compare_inventory(dest / "grilling", meta), [])

    def test_modified_deleted_and_extra_files_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            dest.mkdir()
            meta = self.install(dest)
            (dest / "grilling/SKILL.md").write_text("changed", encoding="utf-8")
            (dest / "grilling/extra.txt").unlink()
            (dest / "grilling/new.txt").write_text("new", encoding="utf-8")
            problems = fetch_skills.compare_inventory(dest / "grilling", meta)
        text = "\n".join(problems)
        self.assertIn("原文件已修改", text)
        self.assertIn("原文件缺失", text)
        self.assertIn("额外未记录文件", text)
        self.assertIn("new.txt", text)

    def test_upstream_metadata_file_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            dest.mkdir()
            work = Path(tmp) / "work"
            src = work / "skills/productivity/grilling"
            src.mkdir(parents=True)
            (src / "SKILL.md").write_text("x", encoding="utf-8")
            (src / ".fetched.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(fetch_skills.InstallError):
                fetch_skills.install_one(dest, "grilling", fetch_skills.MATT, locked_commit(), "agent",
                                         "skills/productivity/grilling", work)
            self.assertFalse((dest / "grilling").exists())

    def test_invalid_metadata_is_reported_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills/grilling"
            dest.mkdir(parents=True)
            (dest / "SKILL.md").write_text("x", encoding="utf-8")
            (dest / ".fetched.json").write_text('{"schema_version": 1}', encoding="utf-8")
            meta, problems = fetch_skills.read_metadata(dest, "grilling")
        self.assertIsNone(meta)
        self.assertTrue(any("skill 字段" in p for p in problems))
        self.assertTrue(any("files 必须是数组" in p for p in problems))

    def test_metadata_with_wrong_repository_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills/grilling"
            dest.mkdir(parents=True)
            (dest / "SKILL.md").write_text("x", encoding="utf-8")
            (dest / ".fetched.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "skill": "grilling",
                    "repository": fetch_skills.FEEL_BETTER,
                    "commit": "a" * 40,
                    "source_path": "skills/productivity/grilling",
                    "flavor": "agent",
                    "files": [],
                }),
                encoding="utf-8",
            )
            meta, problems = fetch_skills.read_metadata(dest, "grilling")
        self.assertIsNone(meta)
        self.assertTrue(any("repository 不是" in p for p in problems))


class OutdatedTest(unittest.TestCase):
    def ready(self, dest: Path, meta: dict | None) -> None:
        skill = dest / "grilling"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        if meta is not None:
            (skill / ".fetched.json").write_text(
                json.dumps(meta, ensure_ascii=False), encoding="utf-8"
            )

    def metadata(self, commit: str) -> dict:
        import hashlib
        digest = hashlib.sha256(b"x").hexdigest()
        return {
            "schema_version": 1,
            "skill": "grilling",
            "repository": fetch_skills.MATT,
            "commit": commit,
            "source_path": "skills/productivity/grilling",
            "flavor": "agent",
            "files": [{"path": "SKILL.md", "sha256": digest}],
        }

    def run_report(self, dest: Path, head: str) -> tuple[int, str, str]:
        sources = fetch_skills.load_sources()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(fetch_skills.shutil, "which", return_value="git"):
            with mock.patch.object(fetch_skills, "remote_head", return_value=head):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = fetch_skills.report_outdated(dest, ["grilling"], sources)
        return code, out.getvalue(), err.getvalue()

    def test_same_commit_reports_consistent(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, self.metadata(commit))
            code, out, err = self.run_report(dest, commit)
        self.assertEqual(code, 0)
        self.assertIn("（一致）", out)
        self.assertIn("与基线一致", out)
        self.assertNotIn("落后 ", out)
        self.assertEqual(err, "")

    def test_different_commit_is_not_called_outdated(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, self.metadata(commit))
            code, out, _ = self.run_report(dest, "f" * 40)
        self.assertEqual(code, 0)
        self.assertIn("不同（尚未核验）", out)
        self.assertNotIn("落后 ", out)

    def test_unknown_source_still_checks_upstream(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, None)
            code, out, _ = self.run_report(dest, commit)
        self.assertEqual(code, 0)
        self.assertIn("来源未知", out)
        self.assertIn("与基线一致", out)

    def test_invalid_metadata_makes_report_incomplete(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, {"schema_version": 1})
            code, _, err = self.run_report(dest, commit)
        self.assertEqual(code, 1)
        self.assertIn("来源记录无效", err)

    def test_remote_failure_sets_exit_code(self) -> None:
        commit = locked_commit()
        sources = fetch_skills.load_sources()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, self.metadata(commit))
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(fetch_skills.shutil, "which", return_value="git"):
                with mock.patch.object(fetch_skills, "remote_head", side_effect=fetch_skills.InstallError("timeout")):
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        code = fetch_skills.report_outdated(dest, ["grilling"], sources)
        self.assertEqual(code, 1)
        self.assertIn("上游查询失败", err.getvalue())

    def test_outdated_does_not_write_anything(self) -> None:
        commit = locked_commit()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            self.ready(dest, self.metadata(commit))
            before = {p: p.read_bytes() for p in dest.rglob("*") if p.is_file()}
            self.run_report(dest, commit)
            after = {p: p.read_bytes() for p in dest.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

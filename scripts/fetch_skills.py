#!/usr/bin/env python3
"""按需拉取初始化剧本衔接段要用的配套 skill：本地没有，才从官方仓库安装固定基线。

用法：
    python fetch_skills.py --dest ~/.workbuddy/skills --check grill-with-docs design
    python fetch_skills.py --dest ~/.claude/skills grill-with-docs design
    python fetch_skills.py --dest ~/.claude/skills --outdated grill-with-docs design

    design 是别名，指代生成项目调度表里的 5 个设计 skill（含 impeccable）。

行为约束：
    * 仅用标准库 + 系统 git。
    * 默认安装 references/SKILL-SOURCES.json 里锁定的完整 commit，不追上游最新分支头。
    * 已存在的 skill 一律跳过、绝不覆盖——使用者本地改过的版本要保住。
    * 安装成功后写 <skill>/.fetched.json：仓库、完整提交、实际目录与原始文件摘要。
    * 只复制 skill 目录、不跑任何安装器，也不执行下载内容。
    * --check 只离线报告；--outdated 联网查询，只报告差异，不安装、不更新。
    * 原样复制、不改任何上游文件（grill-with-docs 的 disable-model-invocation 标志尤其不能动）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES_PATH = ROOT / "references" / "SKILL-SOURCES.json"

MATT = "https://github.com/mattpocock/skills"                              # MIT
IMPECCABLE = "https://github.com/pbakaus/impeccable"                        # Apache-2.0
FEEL_BETTER = "https://github.com/jakubkrehel/make-interfaces-feel-better"  # MIT
VERCEL = "https://github.com/vercel-labs/agent-skills"                      # 仓库未声明许可；只拉到本机，不再分发
SHADCN_VUE = "https://github.com/unovue/shadcn-vue"                         # MIT；skill 在默认分支 dev 上，与官方安装命令一致
UIUX = "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"            # MIT

# 名字 → (仓库, 上游目录)。impeccable 按目标工具分发不同目录，{flavor} 由 --flavor 决定。
SKILLS = {
    "grill-with-docs": (MATT, "skills/engineering/grill-with-docs"),
    "grilling": (MATT, "skills/productivity/grilling"),
    "domain-modeling": (MATT, "skills/engineering/domain-modeling"),
    "impeccable": (IMPECCABLE, ".{flavor}/skills/impeccable"),
    "make-interfaces-feel-better": (FEEL_BETTER, "skills/make-interfaces-feel-better"),
    "web-design-guidelines": (VERCEL, "skills/web-design-guidelines"),
    "shadcn-vue": (SHADCN_VUE, "skills/shadcn-vue"),
    "ui-ux-pro-max": (UIUX, ".claude/skills/ui-ux-pro-max"),
}
# grill-with-docs 只是个转发壳，真正干活的是这两个
DEPENDS = {"grill-with-docs": ["grilling", "domain-modeling"]}
# 别名：一个词指代一组。design = 生成项目的 design-skills.md 调度表里的那 5 个
GROUPS = {
    "design": ["impeccable", "make-interfaces-feel-better", "web-design-guidelines",
               "shadcn-vue", "ui-ux-pro-max"],
}
# 「不是完全体」的说明：拉下来的只是 skill 目录本身，上游仓库里的其他部分刻意不装。
# 清单里会随缺失项一起打印，让使用者在确认前就看到装到哪一步。
NOTES = {
    "impeccable": "只装 skill 目录，不装 hooks（本项目约定不装）；引擎二进制首次调用时才从 GitHub Releases 拉取并执行",
    "ui-ux-pro-max": "只装运行时核心（SKILL.md / scripts / references / data），不含 cli 安装器、templates、gallery；"
                     "⚠️ 上游文档把 --persist 当推荐用法，本项目禁用 --persist / --force",
    "web-design-guidelines": "每次使用时还会联网，从 vercel-labs/web-interface-guidelines 拉最新规则",
    "shadcn-vue": "user-invocable: false，只能 AI 自己用、@ 不到；取上游默认分支 dev",
}

SOURCES_SCHEMA = 1
METADATA_NAME = ".fetched.json"
METADATA_SCHEMA = 1
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^\S+$")


class SourceError(Exception):
    """锁定清单缺失或格式不可用。"""


class InstallError(Exception):
    """固定提交获取或安装失败。"""


# ────────────────────────────── 锁定清单 ──────────────────────────────

def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重复的 JSON 键：{key}")
        result[key] = value
    return result


def load_sources(path: Path | None = None) -> dict:
    path = path or SOURCES_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SourceError(f"锁定清单不存在：{path}") from exc
    except UnicodeDecodeError as exc:
        raise SourceError(f"锁定清单不是 UTF-8 文本：{path}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceError(f"锁定清单解析失败：{path}\n{exc}") from exc
    if not isinstance(data, dict):
        raise SourceError(f"锁定清单顶层必须是对象：{path}")
    return data


def source_problems(sources: dict, skills: dict = SKILLS) -> list[str]:
    """校验锁定清单结构；离线、不判断提交是否仍可下载。"""
    problems: list[str] = []
    if sources.get("schema_version") != SOURCES_SCHEMA:
        problems.append(f"锁定清单 schema_version 必须是 {SOURCES_SCHEMA}")
    repositories = sources.get("repositories")
    if not isinstance(repositories, dict):
        return problems + ["锁定清单缺少 repositories 对象"]

    expected = {repo for repo, _ in skills.values()}
    for repo in sorted(expected - repositories.keys()):
        problems.append(f"锁定清单缺少仓库：{repo}")
    for repo in sorted(repositories.keys() - expected):
        problems.append(f"锁定清单里有未登记的仓库：{repo}")

    for repo, entry in sorted(repositories.items()):
        if not isinstance(entry, dict):
            problems.append(f"{repo}: 锁定项必须是对象")
            continue
        commit = entry.get("commit")
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            problems.append(f"{repo}: commit 必须是 40 位小写完整 SHA")
        branch = entry.get("branch")
        if not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch):
            problems.append(f"{repo}: branch 必须是非空且不含空白的分支名")
    return problems


def repo_entry(sources: dict, repo: str) -> dict:
    try:
        return sources["repositories"][repo]
    except (KeyError, TypeError) as exc:
        raise SourceError(f"锁定清单里没有仓库：{repo}") from exc


# ────────────────────────────── 计划与状态 ──────────────────────────────

def expand_names(requested: list[str]) -> list[str]:
    """递归展开依赖；环在联网前失败，不静默漏装。"""
    wanted: list[str] = []

    def add(name: str, trail: list[str]) -> None:
        if name in trail:
            raise ValueError("依赖环：" + " → ".join(trail + [name]))
        if name in wanted:
            return
        wanted.append(name)
        for dep in DEPENDS.get(name, ()):
            add(dep, trail + [name])

    for name in requested:
        add(name, [])
    return wanted


def skill_state(dest: Path, name: str) -> str:
    """missing / installed / incomplete / file / special。"""
    path = dest / name
    if path.is_symlink():
        return "special"
    if not path.exists():
        return "missing"
    if not path.is_dir():
        return "file"
    if (path / "SKILL.md").is_file():
        return "installed"
    return "incomplete"


def locked_source(tree: set[str], name: str, hint: str) -> str:
    """固定提交下只认登记目录；找不到说明锁定清单或登记路径不一致。"""
    if f"{hint}/SKILL.md" in tree:
        return hint
    raise LookupError(f"锁定提交里找不到 {name} 的登记目录 {hint}（不自动改用它处副本）")


# ────────────────────────────── 安装 ──────────────────────────────

def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


def _force_remove(func, path, _exc):
    # Windows 上 .git 里的对象文件是只读的，rmtree 直接删会失败
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path: Path) -> None:
    if not path.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_remove)
    else:
        shutil.rmtree(path, onerror=_force_remove)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    """原样复制普通文件；符号链接等特殊文件直接拒绝，不静默解引用。"""
    seen: dict[str, str] = {}
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        posix = rel.as_posix()
        key = posix.lower()
        if key in seen and seen[key] != posix:
            raise InstallError(f"上游存在仅大小写不同的路径，拒绝安装：{seen[key]} / {posix}")
        seen[key] = posix
        target = dst / rel
        if path.is_symlink():
            raise InstallError(f"上游含符号链接，拒绝安装：{posix}")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        else:
            raise InstallError(f"上游含特殊文件，拒绝安装：{posix}")


def file_inventory(root: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise InstallError(f"暂存目录里出现符号链接：{path.name}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise InstallError(f"暂存目录里出现特殊文件：{path.name}")
        rel = path.relative_to(root).as_posix()
        if rel == METADATA_NAME:
            continue
        files.append({"path": rel, "sha256": sha256_file(path)})
    return files


def write_json_lf(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def prepare_checkout(work: Path, repo: str, commit: str, names: list[str], flavor: str) -> dict[str, str]:
    """在临时仓库里只取锁定提交，返回 skill → 上游目录。"""
    git("init", "-q", str(work))
    git("remote", "add", "origin", repo, cwd=work)
    git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit, cwd=work)
    fetched = git("rev-parse", "FETCH_HEAD", cwd=work)
    if fetched != commit:
        raise InstallError(f"取到的提交是 {fetched}，与锁定值 {commit} 不一致")
    tree = set(git("ls-tree", "-r", "--name-only", "FETCH_HEAD", cwd=work).splitlines())
    srcs = {n: locked_source(tree, n, SKILLS[n][1].format(flavor=flavor)) for n in names}
    git("sparse-checkout", "init", "--no-cone", cwd=work)
    git("sparse-checkout", "set", *srcs.values(), cwd=work)
    git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=work)
    if git("rev-parse", "HEAD", cwd=work) != commit:
        raise InstallError(f"检出后的提交不是锁定值 {commit}")
    return srcs


def install_one(dest: Path, name: str, repo: str, commit: str, flavor: str,
                src: str, work: Path) -> None:
    source = work / src
    if not (source / "SKILL.md").is_file():
        raise InstallError(f"检出后找不到 SKILL.md：{src}")
    if (source / METADATA_NAME).exists() or (source / METADATA_NAME).is_symlink():
        raise InstallError(f"上游目录已含 {METADATA_NAME}，拒绝覆盖来源记录")
    staging = Path(tempfile.mkdtemp(prefix=f".{name}.partial-", dir=dest))
    published = False
    try:
        copy_tree(source, staging)
        metadata = {
            "schema_version": METADATA_SCHEMA,
            "skill": name,
            "repository": repo,
            "commit": commit,
            "source_path": src,
            "flavor": flavor,
            "files": file_inventory(staging),
        }
        write_json_lf(staging / METADATA_NAME, metadata)

        final = dest / name
        if final.exists() or final.is_symlink():
            raise FileExistsError(f"目标已存在，未覆盖：{final}")
        staging.rename(final)
        published = True
    finally:
        if not published:
            rmtree(staging)


# ────────────────────────────── 来源记录检查 ──────────────────────────────

def _safe_rel(rel: str) -> bool:
    if not rel or rel.startswith("/") or "\\" in rel:
        return False
    return all(part not in ("", ".", "..") for part in rel.split("/"))


def read_metadata(skill_dir: Path, expected_skill: str) -> tuple[dict | None, list[str]]:
    path = skill_dir / METADATA_NAME
    if not path.is_file():
        return None, []
    where = f"{skill_dir.name}/{METADATA_NAME}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [f"{where}: 来源记录无法解析（{exc}）"]
    if not isinstance(data, dict):
        return None, [f"{where}: 顶层必须是对象"]

    problems: list[str] = []
    if data.get("schema_version") != METADATA_SCHEMA:
        problems.append(f"{where}: schema_version 不是 {METADATA_SCHEMA}")
    if data.get("skill") != expected_skill:
        problems.append(f"{where}: skill 字段不是 {expected_skill}")
    repository = data.get("repository")
    expected_repo = SKILLS[expected_skill][0]
    if not isinstance(repository, str) or repository != expected_repo:
        problems.append(f"{where}: repository 不是 {expected_repo}")
    if not isinstance(data.get("commit"), str) or not COMMIT_RE.fullmatch(data["commit"]):
        problems.append(f"{where}: commit 不是 40 位小写完整 SHA")
    if not isinstance(data.get("source_path"), str) or not data["source_path"]:
        problems.append(f"{where}: source_path 缺失")
    if data.get("flavor") not in ("agent", "claude"):
        problems.append(f"{where}: flavor 必须是 agent 或 claude")

    files = data.get("files")
    if not isinstance(files, list):
        problems.append(f"{where}: files 必须是数组")
    else:
        seen: set[str] = set()
        for item in files:
            if not isinstance(item, dict):
                problems.append(f"{where}: files 里有非对象条目")
                continue
            rel, digest = item.get("path"), item.get("sha256")
            if not isinstance(rel, str) or not _safe_rel(rel):
                problems.append(f"{where}: files 里有非法路径：{rel!r}")
            elif rel in seen:
                problems.append(f"{where}: files 里路径重复：{rel}")
            else:
                seen.add(rel)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                problems.append(f"{where}: {rel} 的 sha256 非法")
    return (None, problems) if problems else (data, [])


def compare_inventory(skill_dir: Path, meta: dict) -> list[str]:
    recorded = {item["path"]: item["sha256"] for item in meta["files"]}
    actual: dict[str, str] = {}
    problems: list[str] = []
    for path in sorted(skill_dir.rglob("*")):
        rel = path.relative_to(skill_dir).as_posix()
        if rel == METADATA_NAME:
            continue
        if path.is_symlink():
            problems.append(f"{skill_dir.name}: 存在符号链接：{rel}")
        elif path.is_file():
            actual[rel] = sha256_file(path)

    changed = sorted(p for p in recorded if p in actual and actual[p] != recorded[p])
    deleted = sorted(p for p in recorded if p not in actual)
    extra = sorted(p for p in actual if p not in recorded)
    for label, items in (("原文件已修改", changed), ("原文件缺失", deleted), ("额外未记录文件", extra)):
        if items:
            shown = "、".join(items[:10]) + ("…" if len(items) > 10 else "")
            problems.append(f"{skill_dir.name}: {label}（{len(items)}）：{shown}")
    return problems


# ────────────────────────────── 过期检查 ──────────────────────────────

def remote_head(repo: str, branch: str, timeout: int = 30) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", repo, f"refs/heads/{branch}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallError(f"查询超时（{timeout}s）") from exc
    if result.returncode != 0:
        raise InstallError((result.stderr or "").strip() or f"git 退出码 {result.returncode}")
    line = result.stdout.strip()
    if not line:
        raise InstallError(f"上游没有分支 {branch}")
    return line.split()[0]


def report_outdated(dest: Path, wanted: list[str], sources: dict) -> int:
    if shutil.which("git") is None:
        print("==> 找不到 git，无法查询上游", file=sys.stderr)
        return 1

    failed = False
    repos: list[str] = []
    for name in wanted:
        repo = SKILLS[name][0]
        if repo not in repos:
            repos.append(repo)

    print(f"==> 目标目录：{dest}")
    for name in wanted:
        repo = SKILLS[name][0]
        baseline = repo_entry(sources, repo)["commit"]
        state = skill_state(dest, name)
        if state == "missing":
            print(f"    未安装      {name:<28} 基线 {baseline[:7]}")
            continue
        if state != "installed":
            print(f"    无法检查    {name:<28} 目标不是完整的 skill 目录（{state}）", file=sys.stderr)
            failed = True
            continue

        skill_dir = dest / name
        meta, meta_problems = read_metadata(skill_dir, name)
        if meta_problems:
            print(f"    来源记录无效 {name}", file=sys.stderr)
            for problem in meta_problems:
                print("        " + problem, file=sys.stderr)
            failed = True
        elif meta is None:
            print(f"    已装        {name:<28} 本机 来源未知  基线 {baseline[:7]}")
        else:
            commit = meta["commit"]
            same = commit == baseline
            print(f"    已装        {name:<28} 本机 {commit[:7]}  基线 {baseline[:7]}"
                  f"（{'一致' if same else '不同'}）")
            for problem in compare_inventory(skill_dir, meta):
                print("        " + problem, file=sys.stderr)

    for repo in repos:
        entry = repo_entry(sources, repo)
        branch, baseline = entry["branch"], entry["commit"]
        try:
            head = remote_head(repo, branch)
        except InstallError as exc:
            print(f"    上游查询失败 {repo}（{branch}）：{exc}", file=sys.stderr)
            failed = True
            continue
        state = "一致" if head == baseline else "不同（尚未核验）"
        print(f"    上游        {repo}  {branch}  {head[:7]}  与基线{state}")

    print("\n==> 说明：不同只代表提交号不同，不代表落后或应当升级；本命令不改动任何文件。")
    return 1 if failed else 0


# ────────────────────────────── 入口 ──────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fetch_skills.py", description="本地没有才按固定基线安装配套 skill")
    p.add_argument("names", nargs="+", metavar="SKILL",
                   help=f"可选：{', '.join(SKILLS)}；别名：{', '.join(f'{g}（{len(v)} 个）' for g, v in GROUPS.items())}")
    p.add_argument("--dest", required=True, help="当前 AI 工具的 skill 目录，如 ~/.workbuddy/skills、~/.claude/skills")
    p.add_argument("--flavor", choices=["auto", "agent", "claude"], default="auto",
                   help="impeccable 取上游哪套目录（默认按 --dest 推断：路径含 .claude 取 claude，否则 agent）")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只报告缺哪些、从哪拉；不联网、不写盘")
    mode.add_argument("--outdated", action="store_true",
                      help="联网比较本机记录 / 锁定基线 / 上游分支头；不安装、不更新")
    args = p.parse_args(argv)

    requested = [m for n in args.names for m in GROUPS.get(n, [n])]
    unknown = [n for n in requested if n not in SKILLS]
    if unknown:
        p.error(f"不认识的 skill：{', '.join(unknown)}（可选：{', '.join(SKILLS)}；别名：{', '.join(GROUPS)}）")

    dest = Path(args.dest).expanduser()
    flavor = args.flavor
    if flavor == "auto":
        flavor = "claude" if ".claude" in dest.parts else "agent"

    try:
        sources = load_sources()
    except SourceError as exc:
        print(f"==> 锁定清单不可用：{exc}", file=sys.stderr)
        return 1
    problems = source_problems(sources)
    if problems:
        print("==> 锁定清单结构不合法：", file=sys.stderr)
        for problem in problems:
            print("    " + problem, file=sys.stderr)
        return 1

    try:
        wanted = expand_names(requested)
    except ValueError as exc:
        print(f"==> {exc}", file=sys.stderr)
        return 1

    if args.outdated:
        return report_outdated(dest, wanted, sources)

    print(f"==> 目标目录：{dest}")
    missing: list[str] = []
    blocked: list[str] = []
    for n in wanted:
        repo, src = SKILLS[n]
        commit = repo_entry(sources, repo)["commit"]
        state = skill_state(dest, n)
        labels = {"missing": "缺失", "installed": "已装", "incomplete": "残缺",
                  "file": "冲突", "special": "冲突"}
        label = labels[state]
        print(f"    {label}  {n:<28} ← {repo} @ {commit[:7]}  {src.format(flavor=flavor)}")
        if state == "installed":
            meta, meta_problems = read_metadata(dest / n, n)
            note = "来源未知" if meta is None and not meta_problems else (
                f"来源 {meta['commit'][:7]}" if meta else "来源记录无效")
            print(f"          ↳ {note}")
        elif state == "missing":
            missing.append(n)
            if n in NOTES:
                print(f"          ↳ {NOTES[n]}")
        else:
            blocked.append(n)

    if not missing and not blocked:
        print("==> 都已安装，没有要拉的")
        return 0
    if blocked:
        print(f"==> 有 {len(blocked)} 个目标位置被占用或残缺，未覆盖：{', '.join(blocked)}", file=sys.stderr)
    if args.check:
        print(f"==> 缺 {len(missing)} 个；确认后去掉 --check 再跑一次即可拉取")
        return 0
    if not missing:
        return 1
    if shutil.which("git") is None:
        print("==> 找不到 git，没法拉取", file=sys.stderr)
        return 1

    dest.mkdir(parents=True, exist_ok=True)
    by_repo: dict[str, list[str]] = {}
    for n in missing:
        by_repo.setdefault(SKILLS[n][0], []).append(n)

    installed: list[str] = []
    installed_names: set[str] = set()
    failed: list[str] = []
    for repo, names in by_repo.items():
        commit = repo_entry(sources, repo)["commit"]
        work = Path(tempfile.mkdtemp(prefix="skill-fetch-"))
        try:
            try:
                srcs = prepare_checkout(work, repo, commit, names, flavor)
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or "").strip()
                raise InstallError(f"无法获取锁定提交（需要 git 2.25+ 与可访问的上游）：{detail}") from exc

            for n in names:
                try:
                    install_one(dest, n, repo, commit, flavor, srcs[n], work)
                except (InstallError, OSError) as exc:
                    print(f"    未完成  {n}：{exc}", file=sys.stderr)
                    failed.append(n)
                else:
                    installed_names.add(n)
                    installed.append(f"{n} ← {repo} @ {commit[:7]}")
                    print(f"    已装  {n} @ {commit[:7]}")
        except (InstallError, LookupError, OSError) as exc:
            print(f"==> 拉取失败：{repo} @ {commit[:7]}\n    {exc}", file=sys.stderr)
            failed.extend(n for n in names if n not in installed_names)
        finally:
            rmtree(work)

    if installed:
        print("\n==> 已装好，下面几行写进 worklog：")
        for line in installed:
            print("    " + line)
        print("    多数工具只在会话开始时扫描 skill 目录：当前会话看不到新 skill 时，开一个新会话再触发。")
    if failed:
        print(f"\n==> 未完成：{', '.join(dict.fromkeys(failed))}", file=sys.stderr)
        return 1
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())

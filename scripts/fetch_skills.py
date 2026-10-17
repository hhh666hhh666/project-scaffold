#!/usr/bin/env python3
"""按需拉取初始化剧本衔接段要用的配套 skill：本地没有，才从官方仓库拉最新版。

用法：
    python fetch_skills.py --dest ~/.workbuddy/skills --check grill-with-docs design
    python fetch_skills.py --dest ~/.claude/skills grill-with-docs design

    design 是别名，指代生成项目调度表里的 5 个设计 skill（含 impeccable）。

行为约束：
    * 仅用标准库 + 系统 git。
    * 已存在的 skill 一律跳过、绝不覆盖——使用者本地改过的版本要保住。
    * 拉的是上游默认分支的最新提交；装完打印 commit，供写进 worklog 追溯。
    * blobless 克隆 + 只检出需要的目录，不下载整个仓库的文件内容。
    * 原样复制、不改任何文件（grill-with-docs 的 disable-model-invocation 标志尤其不能动）。
    * 只复制 skill 目录，不跑任何安装器：所以拿到的不是上游的「完全体」——
      不会顺带装上 hooks、CLI 安装器、模板等；各 skill 具体差在哪见 NOTES。
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

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


def locate(tree: set[str], name: str, hint: str) -> str:
    """优先用登记的目录；上游挪了位置，就按 */<name>/SKILL.md 找唯一候选，多于一个不猜。"""
    if f"{hint}/SKILL.md" in tree:
        return hint
    cands = sorted(
        p[: -len("/SKILL.md")] for p in tree
        if p.endswith(f"/{name}/SKILL.md") and not p.startswith("tests/")
    )
    if len(cands) == 1:
        return cands[0]
    raise LookupError(f"上游找不到 {name}（登记位置 {hint}；候选：{', '.join(cands) or '无'}）")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fetch_skills.py", description="本地没有才从官方仓库拉取配套 skill")
    p.add_argument("names", nargs="+", metavar="SKILL",
                   help=f"可选：{', '.join(SKILLS)}；别名：{', '.join(f'{g}（{len(v)} 个）' for g, v in GROUPS.items())}")
    p.add_argument("--dest", required=True, help="当前 AI 工具的 skill 目录，如 ~/.workbuddy/skills、~/.claude/skills")
    p.add_argument("--flavor", choices=["auto", "agent", "claude"], default="auto",
                   help="impeccable 取上游哪套目录（默认按 --dest 推断：路径含 .claude 取 claude，否则 agent）")
    p.add_argument("--check", action="store_true", help="只报告缺哪些、会从哪拉；不联网、不写盘")
    args = p.parse_args(argv)

    requested = [m for n in args.names for m in GROUPS.get(n, [n])]
    unknown = [n for n in requested if n not in SKILLS]
    if unknown:
        p.error(f"不认识的 skill：{', '.join(unknown)}（可选：{', '.join(SKILLS)}；别名：{', '.join(GROUPS)}）")

    dest = Path(args.dest).expanduser()
    flavor = args.flavor
    if flavor == "auto":
        flavor = "claude" if ".claude" in dest.parts else "agent"

    wanted: list[str] = []
    for n in requested:
        for m in (n, *DEPENDS.get(n, ())):
            if m not in wanted:
                wanted.append(m)
    missing = [n for n in wanted if not (dest / n / "SKILL.md").is_file()]

    print(f"==> 目标目录：{dest}")
    for n in wanted:
        repo, src = SKILLS[n]
        state = "缺失" if n in missing else "已装"
        print(f"    {state}  {n:<28} ← {repo}  {src.format(flavor=flavor)}")
        if n in missing and n in NOTES:
            print(f"          ↳ {NOTES[n]}")

    if not missing:
        print("==> 都已安装，没有要拉的")
        return 0
    if args.check:
        print(f"==> 缺 {len(missing)} 个；确认后去掉 --check 再跑一次即可拉取")
        return 0
    if shutil.which("git") is None:
        print("==> 找不到 git，没法拉取", file=sys.stderr)
        return 1

    dest.mkdir(parents=True, exist_ok=True)
    by_repo: dict[str, list[str]] = {}
    for n in missing:
        by_repo.setdefault(SKILLS[n][0], []).append(n)

    installed: list[str] = []
    for repo, names in by_repo.items():
        work = Path(tempfile.mkdtemp(prefix="skill-fetch-"))
        try:
            # 分区克隆：不下载文件内容、只检出需要的目录。
            # impeccable 整仓库近 700 MB，而它的 skill 目录只有 2 MB 左右；实测这一步约 3 秒。
            try:
                git("clone", "--filter=blob:none", "--sparse", "--depth", "1", repo, str(work))
            except subprocess.CalledProcessError:
                rmtree(work)
                print(f"==> 拉取失败：{repo}\n    本机 git 不支持分区克隆（需要 2.25+，当前 "
                      f"{git('--version')}）。升级 git 后再试。", file=sys.stderr)
                return 1

            sha = git("rev-parse", "--short", "HEAD", cwd=work)
            tree = set(git("ls-tree", "-r", "--name-only", "HEAD", cwd=work).splitlines())
            srcs = {n: locate(tree, n, SKILLS[n][1].format(flavor=flavor)) for n in names}
            git("sparse-checkout", "set", *srcs.values(), cwd=work)

            for n, src in srcs.items():
                # 先复制到临时名再改名：中途失败不会留下半个 skill，下次检查也不会误判为「已装」
                staging = dest / f".{n}.partial"
                rmtree(staging)
                shutil.copytree(work / src, staging)
                staging.rename(dest / n)
                installed.append(f"{n} ← {repo} @ {sha}")
                print(f"    已装  {n} @ {sha}")
        except subprocess.CalledProcessError as e:
            print(f"==> 拉取失败：{repo}\n{(e.stderr or '').strip()}", file=sys.stderr)
            return 1
        except (LookupError, OSError) as e:
            print(f"==> 安装失败：{e}", file=sys.stderr)
            return 1
        finally:
            rmtree(work)

    print("\n==> 已装好，下面几行写进 worklog：")
    for line in installed:
        print("    " + line)
    print("    多数工具只在会话开始时扫描 skill 目录：当前会话看不到新 skill 时，开一个新会话再触发。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

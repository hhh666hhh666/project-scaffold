#!/usr/bin/env python3
"""仓库维护检查：确认「文档里写的」与「模板 / 拉取脚本里实际的」没有漂开。

检查三组关系，互不替代：

1. 依赖版本：references/TECH-STACK.md 的版本表 ←→ 模板 pom.xml / package.json / Dockerfile，
   以及 CI 工作流里写死的 JDK / Node 版本。
   只查明确登记过的条目；被 Spring Boot 父 POM 管理的依赖不尝试解析远程有效版本。
2. 配套 skill：fetch_skills.py 的登记表、SKILL-SOURCES.json 的锁定项 ←→ 安装说明与设计规则里的清单表格。
3. 架构图：.dot 源文件 ←→ 渲染出的 .svg ←→ 文档引用，以及图里写死的版本 / 端口 / Python 矩阵。
   具体规则见 check_diagrams.py。

约束：
    * 仅标准库、离线、只读；不调用 git / Maven / npm。
    * 一次列出全部问题，不发现第一处就退出。
    * 需要校验的 Markdown 表格用 `<!-- consistency:...:start/end -->` 标出边界；
      表格单元格里不要出现 `|`（本仓库的这几张表都不需要）。
    * 本脚本只服务脚手架仓库自身，不复制进生成项目。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import fetch_skills
import check_diagrams

POM_NS = "{http://maven.apache.org/POM/4.0.0}"

VERSIONS_MARKER = "consistency:versions"
SOURCE_SKILLS_MARKER = "consistency:source-skills"
DESIGN_SKILLS_MARKER = "consistency:design-skills"

# 版本表里必须出现的标识。多一个、少一个都算不一致——防止改名或误删后检查静默变弱。
REQUIRED_VERSION_IDS = frozenset({
    "spring-boot", "mybatis-plus", "mapstruct", "lombok-mapstruct-binding",
    "jjwt", "springdoc", "jdk", "node", "mysql", "vue", "vite", "tailwindcss",
    "vue-router", "pinia", "typescript", "vitest", "happy-dom",
})

POM_PROPERTIES = {
    "mybatis-plus": "mybatis-plus.version",
    "mapstruct": "mapstruct.version",
    "lombok-mapstruct-binding": "lombok-mapstruct-binding.version",
    "jjwt": "jjwt.version",
    "springdoc": "springdoc.version",
}

FRONTEND_PACKAGES = {
    "vue": ("dependencies", "vue"),
    "vite": ("devDependencies", "vite"),
    "tailwindcss": ("devDependencies", "tailwindcss"),
    "vue-router": ("dependencies", "vue-router"),
    "pinia": ("dependencies", "pinia"),
    "typescript": ("devDependencies", "typescript"),
    "vitest": ("devDependencies", "vitest"),
    "happy-dom": ("devDependencies", "happy-dom"),
}

FROM_RE = re.compile(r"^\s*FROM\s+(\S+)", re.MULTILINE)
NODE_IMAGE_RE = re.compile(r"^node:(\d+)")
JRE_IMAGE_RE = re.compile(r"eclipse-temurin:(\d+)")
JAVA_VERSION_RE = re.compile(r"java-version:\s*['\"]?(\d+)")
NODE_VERSION_RE = re.compile(r"node-version:\s*['\"]?(\d+)")
MYSQL_IMAGE_RE = re.compile(r"(?<![\w/:.])mysql:(\d+)")

# MySQL 镜像写死在多处；每一处都要核对，不能只看第一处。
MYSQL_IMAGE_FILES = (
    "templates/docker/docker-compose.dev.yml",
    "templates/deploy/docker-compose.prod.yml",
    "templates/deploy/.github/workflows/release.yml",
    "templates/backend/src/test/java/${PACKAGE_PATH}/module/example/ExampleApiIT.java",
)

# 工作流里写死的 toolchain 版本。模板升级时漏改这里，生成项目会在另一版 JDK / Node 上跑，
# 而两侧的构建结果未必一致——所以让一致性检查一起盯着。
CI_TOOLCHAIN_FILES = (
    "templates/ci/ci.yml",
    ".github/workflows/full-build.yml",
)
BACKTICK_RE = re.compile(r"`([^`]+)`")
LINK_URL_RE = re.compile(r"\]\((https://[^)\s]+)\)")
SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")

SOURCE_TABLES = (
    ("README.md", SOURCE_SKILLS_MARKER),
    ("references/POST-SCAFFOLD.md", SOURCE_SKILLS_MARKER),
)
DESIGN_TABLES = (
    ("templates/rules/design-skills.md", DESIGN_SKILLS_MARKER),
    ("templates/docs/design/设计skill清单.md", DESIGN_SKILLS_MARKER),
)


class Checker:
    """收集问题而不是抛异常：同一轮里尽量把能查的都查完。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.problems: list[str] = []

    def fail(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    def read(self, rel: str) -> str | None:
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.fail(rel, "文件不存在")
        except UnicodeDecodeError as exc:
            self.fail(rel, f"不是 UTF-8 文本（{exc}）")
        return None


# ────────────────────────────── Markdown 表格 ──────────────────────────────

def marked_table(checker: Checker, rel: str, marker: str) -> tuple[list[str], list[list[str]]] | None:
    """取出标记边界内唯一一张表，返回 (表头, 数据行)。"""
    text = checker.read(rel)
    if text is None:
        return None
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    for token in (start, end):
        count = text.count(token)
        if count != 1:
            checker.fail(rel, f"标记 {token} 应出现 1 次，实际 {count} 次")
            return None
    block = text.split(start, 1)[1].split(end, 1)[0]

    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        checker.fail(rel, f"{marker} 标记之间没有可解析的表格")
        return None
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    header, separator, body = rows[0], rows[1], rows[2:]
    if len(separator) != len(header) or not all(SEPARATOR_RE.match(cell) for cell in separator):
        checker.fail(rel, f"{marker} 表格缺少分隔行，或列数与表头不一致")
        return None
    for index, row in enumerate(body, start=1):
        if len(row) != len(header):
            checker.fail(rel, f"{marker} 表格第 {index} 行有 {len(row)} 列，表头是 {len(header)} 列")
            return None
    return header, body


def column(header: list[str], *needles: str) -> int | None:
    for needle in needles:
        for index, name in enumerate(header):
            if needle.lower() in name.lower():
                return index
    return None


def cell_text(cell: str) -> str:
    """表格里用来标识 skill 的写法：优先取第一个反引号片段，否则取加粗的裸名字。"""
    match = BACKTICK_RE.search(cell)
    if match:
        return match.group(1).strip()
    plain = cell.strip().strip("*").strip()
    return plain if re.fullmatch(r"[a-z0-9-]+", plain) else ""


def cell_url(cell: str) -> str:
    match = LINK_URL_RE.search(cell)
    return match.group(1).rstrip("/") if match else ""


# ────────────────────────────── 依赖版本 ──────────────────────────────

def pom_versions(text: str) -> dict[str, str]:
    """从 pom.xml 取登记过的版本；缺节点时用空串，由调用方报错。"""
    root = ET.fromstring(text)
    parent = root.find(f"{POM_NS}parent")
    properties = root.find(f"{POM_NS}properties")
    values: dict[str, str] = {
        "spring-boot": (parent.findtext(f"{POM_NS}version") if parent is not None else "") or "",
        "jdk": (properties.findtext(f"{POM_NS}java.version") if properties is not None else "") or "",
    }
    for key, prop in POM_PROPERTIES.items():
        values[key] = (properties.findtext(f"{POM_NS}{prop}") if properties is not None else "") or ""
    return values


def image_version(text: str, pattern: re.Pattern[str]) -> str:
    for image in FROM_RE.findall(text):
        match = pattern.match(image)
        if match:
            return match.group(1)
    return ""


def first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def check_versions(root: Path) -> list[str]:
    checker = Checker(root)

    pom_path = "templates/backend/pom.xml"
    pom_text = checker.read(pom_path)
    pom: dict[str, str] = {}
    if pom_text is not None:
        try:
            pom = pom_versions(pom_text)
        except ET.ParseError as exc:
            checker.fail(pom_path, f"XML 解析失败：{exc}")

    backend_docker = checker.read("templates/backend/Dockerfile")
    frontend_docker = checker.read("templates/frontend/Dockerfile")
    package_text = checker.read("templates/frontend/package.json")
    package: dict[str, object] = {}
    if package_text is not None:
        try:
            package = json.loads(package_text)
        except json.JSONDecodeError as exc:
            checker.fail("templates/frontend/package.json", f"JSON 解析失败：{exc}")

    table = marked_table(checker, "references/TECH-STACK.md", VERSIONS_MARKER)
    if table is None:
        return checker.problems
    header, rows = table
    id_col = column(header, "标识", "id")
    value_col = column(header, "版本", "version")
    if id_col is None or value_col is None:
        checker.fail("references/TECH-STACK.md", "版本表需要「标识」与「版本」两列")
        return checker.problems

    declared: dict[str, str] = {}
    for row in rows:
        key, value = cell_text(row[id_col]), row[value_col].strip().strip("`").strip()
        if not key:
            checker.fail("references/TECH-STACK.md", f"版本表的标识单元格无法识别：{row[id_col]!r}")
            continue
        if key in declared:
            checker.fail("references/TECH-STACK.md", f"版本表里 {key} 出现了不止一次")
            continue
        declared[key] = value

    for key in sorted(REQUIRED_VERSION_IDS - declared.keys()):
        checker.fail("references/TECH-STACK.md", f"版本表缺少登记项：{key}")
    for key in sorted(declared.keys() - REQUIRED_VERSION_IDS):
        checker.fail("references/TECH-STACK.md", f"版本表里有未登记的标识：{key}")

    def compare(key: str, actual: str, where: str) -> None:
        expected = declared.get(key)
        if expected is None:
            return
        if not actual:
            checker.fail(where, f"取不到 {key} 的版本（节点或镜像标记缺失）")
        elif actual != expected:
            checker.fail(where, f"{key} 版本表写的是 {expected}，实际是 {actual}")

    compare("spring-boot", pom.get("spring-boot", ""), pom_path)
    for key in POM_PROPERTIES:
        compare(key, pom.get(key, ""), pom_path)

    if backend_docker is not None:
        jre = image_version(backend_docker, JRE_IMAGE_RE)
        compare("jdk", pom.get("jdk", ""), f"{pom_path} 的 java.version")
        compare("jdk", jre, "templates/backend/Dockerfile 的 JRE 镜像")
    if frontend_docker is not None:
        compare("node", image_version(frontend_docker, NODE_IMAGE_RE), "templates/frontend/Dockerfile")

    for rel in CI_TOOLCHAIN_FILES:
        text = checker.read(rel)
        if text is None:
            continue
        compare("jdk", first_match(JAVA_VERSION_RE, text), f"{rel} 的 java-version")
        compare("node", first_match(NODE_VERSION_RE, text), f"{rel} 的 node-version")

    for rel in MYSQL_IMAGE_FILES:
        text = checker.read(rel)
        if text is None:
            continue
        found = MYSQL_IMAGE_RE.findall(text)
        if not found:
            checker.fail(rel, "找不到 mysql:<版本> 镜像标记")
            continue
        for actual in sorted(set(found)):
            compare("mysql", actual, f"{rel} 的 MySQL 镜像")

    for key, (section, name) in FRONTEND_PACKAGES.items():
        actual = ""
        if isinstance(package.get(section), dict):
            actual = str(package[section].get(name) or "")
        compare(key, actual, f"templates/frontend/package.json 的 {section}.{name}")

    # Tailwind 的两个包同版本发布：只登记一个值，另一个必须与它一致。
    if isinstance(package.get("devDependencies"), dict):
        deps = package["devDependencies"]
        tailwind, vite_plugin = str(deps.get("tailwindcss") or ""), str(deps.get("@tailwindcss/vite") or "")
        if not tailwind or not vite_plugin:
            checker.fail("templates/frontend/package.json", "tailwindcss 与 @tailwindcss/vite 必须同时存在")
        elif tailwind != vite_plugin:
            checker.fail(
                "templates/frontend/package.json",
                f"tailwindcss={tailwind} 与 @tailwindcss/vite={vite_plugin} 声明不一致（两者同版本发布）",
            )

    return checker.problems


# ────────────────────────────── 配套 skill ──────────────────────────────

def registry_problems(root: Path | None = None) -> list[str]:
    """先查登记表自身：分组、依赖、备注、来源地址与锁定清单都不能自相矛盾。"""
    problems: list[str] = []
    skills = fetch_skills.SKILLS

    sources_path = (root or fetch_skills.ROOT) / "references" / "SKILL-SOURCES.json"
    try:
        sources = fetch_skills.load_sources(sources_path)
    except fetch_skills.SourceError as exc:
        problems.append(str(exc))
    else:
        problems.extend(fetch_skills.source_problems(sources))

    for name, (repo, src) in sorted(skills.items()):
        if not repo.startswith("https://github.com/"):
            problems.append(f"fetch_skills.SKILLS[{name}]: 来源地址不是 GitHub 仓库：{repo}")
        if not src.strip():
            problems.append(f"fetch_skills.SKILLS[{name}]: 上游目录为空")
        for flavor in ("agent", "claude"):
            try:
                path = src.format(flavor=flavor)
            except (KeyError, IndexError) as exc:
                problems.append(f"fetch_skills.SKILLS[{name}]: 上游目录模板有未知占位符（{exc}）")
                continue
            if not path.strip() or "{" in path or "}" in path:
                problems.append(f"fetch_skills.SKILLS[{name}]: {flavor} 口径的上游目录无效：{path!r}")

    for group, members in sorted(fetch_skills.GROUPS.items()):
        if not members:
            problems.append(f"fetch_skills.GROUPS[{group}]: 分组为空")
        for member in members:
            if member not in skills:
                problems.append(f"fetch_skills.GROUPS[{group}]: 成员 {member} 没有登记在 SKILLS")
        if len(set(members)) != len(members):
            problems.append(f"fetch_skills.GROUPS[{group}]: 成员有重复")

    for name, deps in sorted(fetch_skills.DEPENDS.items()):
        if name not in skills:
            problems.append(f"fetch_skills.DEPENDS[{name}]: 这个 skill 没有登记在 SKILLS")
        for dep in deps:
            if dep not in skills:
                problems.append(f"fetch_skills.DEPENDS[{name}]: 依赖 {dep} 没有登记在 SKILLS")
            if dep == name:
                problems.append(f"fetch_skills.DEPENDS[{name}]: 不能依赖自己")

    for name in sorted(fetch_skills.NOTES):
        if name not in skills:
            problems.append(f"fetch_skills.NOTES[{name}]: 没有登记在 SKILLS")

    # 依赖环：沿 DEPENDS 走一遍 DFS，碰到栈上的节点就是环。
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: str, trail: list[str]) -> None:
        if node in done:
            return
        if node in visiting:
            problems.append("fetch_skills.DEPENDS: 存在依赖环：" + " → ".join(trail + [node]))
            return
        visiting.add(node)
        for dep in fetch_skills.DEPENDS.get(node, ()):
            if dep in skills:
                walk(dep, trail + [node])
        visiting.discard(node)
        done.add(node)

    for name in sorted(skills):
        walk(name, [])

    return problems


def check_skills(root: Path) -> list[str]:
    checker = Checker(root)
    for problem in registry_problems(root):
        checker.problems.append(problem)

    design = set(fetch_skills.GROUPS.get("design", ()))
    expected_source = design | {"grill-with-docs"}

    for rel, marker in SOURCE_TABLES:
        table = marked_table(checker, rel, marker)
        if table is None:
            continue
        header, rows = table
        name_col = column(header, "skill")
        repo_col = column(header, "官方仓库", "仓库")
        if name_col is None or repo_col is None:
            checker.fail(rel, "来源表需要「skill」与「官方仓库」两列")
            continue
        seen: dict[str, str] = {}
        for row in rows:
            name = cell_text(row[name_col])
            if not name:
                checker.fail(rel, f"来源表有一行的 skill 单元格无法识别：{row[name_col]!r}")
                continue
            if name in seen:
                checker.fail(rel, f"来源表里 {name} 出现了不止一次")
                continue
            seen[name] = cell_url(row[repo_col])
        for name in sorted(expected_source - seen.keys()):
            checker.fail(rel, f"来源表缺少 skill：{name}")
        for name in sorted(seen.keys() - expected_source):
            checker.fail(rel, f"来源表里有未登记的 skill：{name}")
        for name in sorted(seen.keys() & expected_source):
            repo = seen[name]
            expected_repo = fetch_skills.SKILLS[name][0].rstrip("/")
            if not repo:
                checker.fail(rel, f"{name} 的官方仓库链接缺失")
            elif repo != expected_repo:
                checker.fail(rel, f"{name} 的官方仓库写的是 {repo}，脚本里是 {expected_repo}")

    for rel, marker in DESIGN_TABLES:
        table = marked_table(checker, rel, marker)
        if table is None:
            continue
        header, rows = table
        name_col = column(header, "skill", "用哪个")
        if name_col is None:
            checker.fail(rel, "设计清单需要「Skill」或「用哪个」列")
            continue
        seen: list[str] = []
        for row in rows:
            name = cell_text(row[name_col])
            if not name:
                checker.fail(rel, f"设计清单有一行的 skill 单元格无法识别：{row[name_col]!r}")
                continue
            if name in seen:
                checker.fail(rel, f"设计清单里 {name} 出现了不止一次")
                continue
            seen.append(name)
        for name in sorted(design - set(seen)):
            checker.fail(rel, f"设计清单缺少 skill：{name}")
        for name in sorted(set(seen) - design):
            checker.fail(rel, f"设计清单里有未登记的 skill：{name}")

    return checker.problems


# ────────────────────────────── 入口 ──────────────────────────────

def check_all(root: Path = ROOT) -> list[str]:
    return check_versions(root) + check_skills(root) + check_diagrams.check_diagrams(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_consistency.py",
        description="检查依赖版本、配套 skill 清单与架构图是否与源文件一致（离线、只读）",
    )
    parser.add_argument("--only", choices=["all", "versions", "skills", "diagrams"], default="all",
                        help="只跑其中一组检查（默认 all）")
    args = parser.parse_args(argv)

    groups = {
        "versions": ("依赖版本", check_versions),
        "skills": ("配套 skill 清单", check_skills),
        "diagrams": ("架构图与源文件", check_diagrams.check_diagrams),
    }
    selected = groups if args.only == "all" else {args.only: groups[args.only]}

    problems: list[str] = []
    for label, check in selected.values():
        print(f"==> {label}")
        found = check(ROOT)
        problems.extend(found)
        if not found:
            print("    通过")

    if problems:
        print(f"\n==> 发现 {len(problems)} 处不一致：", file=sys.stderr)
        for problem in problems:
            print("    " + problem, file=sys.stderr)
        return 1
    print("\n==> 通过：所选检查全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

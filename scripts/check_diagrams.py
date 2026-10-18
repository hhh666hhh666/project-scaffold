#!/usr/bin/env python3
"""架构图防漂移检查：确认 Graphviz 源文件、渲染出的 SVG 与文档引用三者一致。

检查三组关系：

1. 文件对应：登记过的每张图都有 `.dot` 与 `.svg`；`references/` 下没有未登记的图。
2. 结构与文字：解析 `.dot` 的节点 / 簇 / 边，与 SVG 里的 `<title>`、`<text>` 比对。
   只改 `.dot` 不重新渲染，或只改 SVG，都会在这里暴露。
3. 图里的事实：版本、端口、Python 矩阵等登记过的写法，必须与版本表 / 脚本 / 工作流一致。

约束：
    * 仅标准库、离线、只读；不调用 Graphviz，也不联网。
    * DOT 只支持本仓库用到的子集；遇到不支持的写法明确报错，不静默放过。
    * 不检查纯样式（颜色、布局、rankdir）与文字是否重叠——那些不属于漂移。
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 登记表：新增图必须同时加到这里，否则 references/ 下的 .dot / .svg 会被判为未登记。
DIAGRAMS = (
    "architecture",
    "architecture-runtime",
    "architecture-quality",
    "architecture-selftest",
)

DOC_FILES = ("README.md", "SKILL.md")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
VERSION_ROW_RE = re.compile(r"(?m)^\|\s*`([a-z0-9-]+)`\s*\|[^|]*\|\s*`([^`]+)`\s*\|")


class DiagramError(Exception):
    """DOT / SVG 无法按本仓库支持的子集解析。"""


# ────────────────────────────── DOT 解析 ──────────────────────────────

class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value: str, line: int) -> None:
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"Token({self.kind!r}, {self.value!r}, {self.line})"


def _unescape(raw: str, line: int) -> str:
    out: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        if index + 1 >= len(raw):
            raise DiagramError(f"第 {line} 行：字符串以孤立反斜杠结尾")
        escape = raw[index + 1]
        if escape in "nlr":
            out.append("\n")
        elif escape == '"':
            out.append('"')
        elif escape == "\\":
            out.append("\\")
        elif escape in "NEG":
            raise DiagramError(f"第 {line} 行：不支持 Graphviz 内置替换 \\{escape}")
        else:
            out.append("\\" + escape)
        index += 2
    return "".join(out)


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index, line = 0, 1
    line_start = True
    length = len(text)

    while index < length:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            line_start = True
            continue
        if char in " \t\r":
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            if end < 0:
                raise DiagramError(f"第 {line} 行：块注释没有结束")
            line += text.count("\n", index, end)
            index = end + 2
            continue
        if char == "#" and line_start:
            while index < length and text[index] != "\n":
                index += 1
            continue

        line_start = False
        if char == '"':
            start_line = line
            index += 1
            raw: list[str] = []
            while index < length and text[index] != '"':
                if text[index] == "\n":
                    line += 1
                raw.append(text[index])
                index += 1
            if index >= length:
                raise DiagramError(f"第 {start_line} 行：字符串没有结束引号")
            index += 1
            tokens.append(Token("str", _unescape("".join(raw), start_line), start_line))
            continue
        if text.startswith("->", index):
            tokens.append(Token("sym", "->", line))
            index += 2
            continue
        if char in "{}[]=;,:":
            tokens.append(Token("sym", char, line))
            index += 1
            continue
        if char.isalnum() or char in "_.":
            start = index
            while index < length and (text[index].isalnum() or text[index] in "_."):
                index += 1
            tokens.append(Token("id", text[start:index], line))
            continue
        raise DiagramError(f"第 {line} 行：不支持的字符 {char!r}")

    tokens.append(Token("eof", "", line))
    return tokens


def label_lines(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return tuple(line.strip() for line in lines if line.strip())


class DotModel:
    def __init__(self) -> None:
        self.nodes: dict[str, tuple[str, ...]] = {}
        self.clusters: dict[str, tuple[str, ...]] = {}
        self.edges: list[tuple[str, str, tuple[str, ...]]] = []


class DotParser:
    def __init__(self, text: str, source: str = "<dot>") -> None:
        self.tokens = tokenize(text)
        self.index = 0
        self.source = source
        self.model = DotModel()

    # ── token helpers ──

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.index + offset, len(self.tokens) - 1)]

    def next(self) -> Token:
        token = self.peek()
        self.index += 1
        return token

    def fail(self, token: Token, message: str) -> None:
        raise DiagramError(f"{self.source} 第 {token.line} 行：{message}")

    def expect_symbol(self, symbol: str) -> Token:
        token = self.peek()
        if token.kind != "sym" or token.value != symbol:
            self.fail(token, f"期望 {symbol!r}，实际是 {token.value!r}")
        return self.next()

    def expect_id(self) -> str:
        token = self.peek()
        if token.kind in ("id", "str"):
            return self.next().value
        if token.kind == "sym" and token.value == "{":
            self.fail(token, "不支持以子图作为边的端点")
        self.fail(token, f"期望节点名，实际是 {token.value!r}")

    def parse_value(self) -> str:
        token = self.peek()
        if token.kind in ("id", "str"):
            return self.next().value
        self.fail(token, f"期望属性值，实际是 {token.value!r}")

    # ── entry ──

    def parse(self) -> DotModel:
        token = self.peek()
        if token.kind == "id" and token.value.lower() == "strict":
            self.fail(token, "不支持 strict 图")
        if not (token.kind == "id" and token.value.lower() == "digraph"):
            self.fail(token, "只支持 digraph（有向图）")
        self.next()
        if self.peek().kind in ("id", "str"):
            self.next()
        self.expect_symbol("{")
        self.parse_statements(None)
        self.expect_symbol("}")
        if self.peek().kind != "eof":
            self.fail(self.peek(), "图结束后还有多余内容")
        return self.model

    # ── statements ──

    def parse_statements(self, cluster: str | None) -> str | None:
        cluster_label: str | None = None

        while True:
            token = self.peek()
            if token.kind == "eof":
                self.fail(token, "缺少右花括号 }")
            if token.kind == "sym" and token.value == "}":
                return cluster_label
            if token.kind == "sym" and token.value in (";", ","):
                self.next()
                continue
            if token.kind == "sym" and token.value == "{":
                self.next()
                self.parse_statements(None)
                self.expect_symbol("}")
                continue
            if token.kind == "sym" and token.value == ":":
                self.fail(token, "不支持端口写法（a:port）")
            if token.kind != "id":
                self.fail(token, f"无法解析的语句起始：{token.value!r}")

            word = token.value.lower()
            if word in ("node", "edge", "graph") and self._next_is_attr_list():
                self.next()
                self.parse_attrs()
                continue
            if word == "subgraph":
                self.next()
                name = None
                if self.peek().kind in ("id", "str"):
                    name = self.next().value
                self.expect_symbol("{")
                is_cluster = bool(name and name.lower().startswith("cluster"))
                label = self.parse_statements(name if is_cluster else None)
                self.expect_symbol("}")
                if is_cluster:
                    self.model.clusters[name] = label_lines(label)
                continue

            if self._next_is_assignment():
                key = self.next().value.lower()
                self.next()  # '='
                value = self.parse_value()
                if key == "label" and cluster is not None:
                    cluster_label = value
                continue

            if self._next_is_edge():
                self.parse_edge_chain()
                continue

            node_id = self.next().value
            attrs = self.parse_attrs() if self._at_attr_list() else {}
            self.register_node(node_id, attrs.get("label"))

    def _next_is_attr_list(self) -> bool:
        token = self.peek(1)
        return token.kind == "sym" and token.value == "["

    def _at_attr_list(self) -> bool:
        token = self.peek()
        return token.kind == "sym" and token.value == "["

    def _next_is_assignment(self) -> bool:
        token = self.peek(1)
        return token.kind == "sym" and token.value == "="

    def _next_is_edge(self) -> bool:
        token = self.peek(1)
        return token.kind == "sym" and token.value == "->"

    def parse_attrs(self) -> dict[str, str]:
        self.expect_symbol("[")
        attrs: dict[str, str] = {}
        while True:
            token = self.peek()
            if token.kind == "sym" and token.value == "]":
                self.next()
                return attrs
            if token.kind == "sym" and token.value in (",", ";"):
                self.next()
                continue
            if token.kind not in ("id", "str"):
                self.fail(token, f"属性表里期望键名，实际是 {token.value!r}")
            key = self.next().value.lower()
            self.expect_symbol("=")
            attrs[key] = self.parse_value()

    def register_node(self, node_id: str, label: str | None) -> None:
        if node_id not in self.model.nodes:
            self.model.nodes[node_id] = label_lines(label if label is not None else node_id)
        elif label is not None:
            self.model.nodes[node_id] = label_lines(label)

    def parse_edge_chain(self) -> None:
        chain = [self.expect_id()]
        while self.peek().kind == "sym" and self.peek().value == "->":
            self.next()
            chain.append(self.expect_id())
        attrs = self.parse_attrs() if self._at_attr_list() else {}
        label = label_lines(attrs.get("label"))
        for start, end in zip(chain, chain[1:]):
            self.register_node(start, None)
            self.register_node(end, None)
            self.model.edges.append((start, end, label))


def parse_dot(text: str, source: str = "<dot>") -> DotModel:
    return DotParser(text, source).parse()


# ────────────────────────────── SVG 解析 ──────────────────────────────

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text_content(element: ET.Element) -> str:
    return "".join(element.itertext())


class SvgModel:
    def __init__(self) -> None:
        self.nodes: dict[str, tuple[str, ...]] = {}
        self.clusters: dict[str, tuple[str, ...]] = {}
        self.edges: list[tuple[str, str, tuple[str, ...]]] = []


def parse_svg(text: str, source: str = "<svg>") -> SvgModel:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DiagramError(f"{source}: XML 解析失败：{exc}") from exc

    model = SvgModel()
    for element in root.iter():
        if _local_name(element.tag) != "g":
            continue
        kind = element.get("class")
        if kind not in ("node", "edge", "cluster"):
            continue
        title_element = next(
            (child for child in element if _local_name(child.tag) == "title"), None
        )
        title = _text_content(title_element).strip() if title_element is not None else ""
        lines = tuple(
            _text_content(child).strip()
            for child in element
            if _local_name(child.tag) == "text" and _text_content(child).strip()
        )
        if kind == "node":
            model.nodes[title] = lines
        elif kind == "cluster":
            model.clusters[title] = lines
        else:
            parts = title.split("->")
            if len(parts) != 2:
                raise DiagramError(f"{source}: 无法识别边标题 {title!r}")
            model.edges.append((parts[0].strip(), parts[1].strip(), lines))
    return model


# ────────────────────────────── 结构与引用 ──────────────────────────────

def _format_lines(lines: tuple[str, ...]) -> str:
    return " / ".join(lines) if lines else "（空）"


def compare_models(dot: DotModel, svg: SvgModel, dot_rel: str, svg_rel: str) -> list[str]:
    problems: list[str] = []

    for name in sorted(set(dot.nodes) - set(svg.nodes)):
        problems.append(f"{svg_rel}: 缺少节点 {name}（{dot_rel} 里有），多半是没有重新渲染")
    for name in sorted(set(svg.nodes) - set(dot.nodes)):
        problems.append(f"{svg_rel}: 多出节点 {name}（{dot_rel} 里没有），多半是 SVG 过期")
    for name in sorted(set(dot.nodes) & set(svg.nodes)):
        if dot.nodes[name] != svg.nodes[name]:
            problems.append(
                f"{svg_rel}: 节点 {name} 的文字与 {dot_rel} 不一致"
                f"（图源：{_format_lines(dot.nodes[name])}；SVG：{_format_lines(svg.nodes[name])}）"
            )

    for name in sorted(set(dot.clusters) - set(svg.clusters)):
        problems.append(f"{svg_rel}: 缺少簇 {name}（{dot_rel} 里有）")
    for name in sorted(set(svg.clusters) - set(dot.clusters)):
        problems.append(f"{svg_rel}: 多出簇 {name}（{dot_rel} 里没有）")
    for name in sorted(set(dot.clusters) & set(svg.clusters)):
        if dot.clusters[name] != svg.clusters[name]:
            problems.append(
                f"{svg_rel}: 簇 {name} 的标题与 {dot_rel} 不一致"
                f"（图源：{_format_lines(dot.clusters[name])}；SVG：{_format_lines(svg.clusters[name])}）"
            )

    dot_edges = Counter(dot.edges)
    svg_edges = Counter(svg.edges)
    for edge in sorted((dot_edges - svg_edges).elements()):
        start, end, label = edge
        problems.append(
            f"{svg_rel}: 缺少边 {start} -> {end}（标签：{_format_lines(label)}），多半是没有重新渲染"
        )
    for edge in sorted((svg_edges - dot_edges).elements()):
        start, end, label = edge
        problems.append(
            f"{svg_rel}: 多出边 {start} -> {end}（标签：{_format_lines(label)}），多半是 SVG 过期"
        )

    return problems


def check_references(root: Path) -> list[str]:
    problems: list[str] = []
    references = root / "references"

    for name in DIAGRAMS:
        dot_path = references / f"{name}.dot"
        svg_path = references / f"{name}.svg"
        for path in (dot_path, svg_path):
            if not path.is_file():
                problems.append(f"{path.relative_to(root).as_posix()}: 登记过的图缺少文件")

    known = set(DIAGRAMS)
    for path in sorted(references.glob("*.dot")) + sorted(references.glob("*.svg")):
        if path.stem not in known:
            problems.append(
                f"{path.relative_to(root).as_posix()}: 未登记的图（新增图需要加进 check_diagrams.DIAGRAMS）"
            )

    markdown_files = [root / name for name in DOC_FILES]
    markdown_files += sorted(references.glob("*.md"))
    referenced: set[Path] = set()
    for markdown in markdown_files:
        if not markdown.is_file():
            problems.append(f"{markdown.relative_to(root).as_posix()}: 文档不存在")
            continue
        text = markdown.read_text(encoding="utf-8")
        for match in IMAGE_RE.finditer(text):
            target = match.group(1).split("#", 1)[0]
            if not target.endswith(".svg") or target.startswith(("http://", "https://")):
                continue
            resolved = (markdown.parent / target).resolve()
            if not resolved.is_file():
                problems.append(
                    f"{markdown.relative_to(root).as_posix()}: 图片链接指向不存在的文件 {target}"
                )
            referenced.add(resolved)

    for name in DIAGRAMS:
        svg_path = (references / f"{name}.svg").resolve()
        if svg_path.is_file() and svg_path not in referenced:
            problems.append(
                f"{svg_path.relative_to(root).as_posix()}: 没有被任何 Markdown 以图片形式引用"
            )

    return problems


# ────────────────────────────── 图中事实 ──────────────────────────────

def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _safe_read(root: Path, rel: str, problems: list[str]) -> str:
    try:
        return _read(root, rel)
    except (OSError, UnicodeDecodeError) as exc:
        problems.append(f"{rel}: 无法读取：{exc}")
        return ""


def _version_table(root: Path) -> dict[str, str]:
    text = _read(root, "references/TECH-STACK.md")
    return {key: value for key, value in VERSION_ROW_RE.findall(text)}


def _major(version: str) -> str:
    return re.sub(r"^[\^~=v]+", "", version).split(".", 1)[0]


def _minor(version: str) -> str:
    return ".".join(re.sub(r"^[\^~=v]+", "", version).split(".")[:2])


def _default_arguments(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("backend-port", "frontend-port", "web-port"):
        match = re.search(rf'"--{name}"[^)]*?default=(\d+)', text)
        if match:
            result[name] = match.group(1)
    return result


def check_facts(root: Path) -> list[str]:
    problems: list[str] = []

    try:
        declared = _version_table(root)
    except (OSError, UnicodeDecodeError) as exc:
        return [f"references/TECH-STACK.md: 无法读取版本表：{exc}"]

    required = ("spring-boot", "vue", "tailwindcss", "node")
    missing = [key for key in required if key not in declared]
    if missing:
        return [f"references/TECH-STACK.md: 版本表缺少登记项 {', '.join(missing)}，无法核对图内事实"]

    selftest_text = _safe_read(root, ".github/workflows/selftest.yml", problems)
    matrix_match = re.search(r"python-version:\s*\[([^\]]+)\]", selftest_text)
    python_versions = re.findall(r"([0-9]+\.[0-9]+)", matrix_match.group(1)) if matrix_match else []
    if not python_versions:
        problems.append(".github/workflows/selftest.yml: 找不到 Python 版本矩阵")

    full_build_text = _safe_read(root, ".github/workflows/full-build.yml", problems)
    node_match = re.search(r"node-version:\s*['\"]?(\d+)", full_build_text)
    workflow_node = node_match.group(1) if node_match else ""
    if not workflow_node:
        problems.append(".github/workflows/full-build.yml: 找不到 node-version")

    ports = _default_arguments(_safe_read(root, "scripts/scaffold.py", problems))
    for name in ("backend-port", "frontend-port", "web-port"):
        if name not in ports:
            problems.append(f"scripts/scaffold.py: 找不到 --{name} 的默认值")

    facts: list[tuple[str, str, str, str]] = [
        ("references/architecture-selftest.dot",
         r"Python job\\n([0-9.]+(?: / [0-9.]+)+)",
         " / ".join(python_versions),
         "Python 版本矩阵"),
        ("references/architecture-runtime.dot",
         r"Spring Boot (\d+\.\d+)",
         _minor(declared["spring-boot"]),
         "Spring Boot 主次版本"),
        ("references/architecture-runtime.dot", r"Vue (\d+)", _major(declared["vue"]), "Vue 主版本"),
        ("references/architecture-runtime.dot",
         r"Tailwind v(\d+)", _major(declared["tailwindcss"]), "Tailwind 主版本"),
        ("references/architecture-runtime.dot",
         r"Vite dev server :(\d+)", ports.get("frontend-port", ""), "前端 dev 端口"),
        ("references/architecture-runtime.dot",
         r"127\.0\.0\.1:(\d+)", ports.get("backend-port", ""), "后端端口"),
        ("references/architecture-runtime.dot",
         r"nginx :(\d+)", ports.get("web-port", ""), "web 端口"),
        ("references/TECH-ARCHITECTURE.md",
         r"Spring Boot (\d+\.\d+)",
         _minor(declared["spring-boot"]),
         "Spring Boot 主次版本"),
        ("references/TECH-ARCHITECTURE.md", r"Vue (\d+)", _major(declared["vue"]), "Vue 主版本"),
        ("references/TECH-ARCHITECTURE.md",
         r"Tailwind v(\d+)", _major(declared["tailwindcss"]), "Tailwind 主版本"),
        ("references/TECH-ARCHITECTURE.md",
         r"node:(\d+)-slim", declared["node"], "Node 主版本"),
        ("references/TECH-ARCHITECTURE.md",
         r"浏览器 :(\d+) → Vite", ports.get("frontend-port", ""), "前端 dev 端口"),
        ("references/TECH-ARCHITECTURE.md",
         r"Spring Boot :(\d+)", ports.get("backend-port", ""), "后端端口"),
        ("references/TECH-ARCHITECTURE.md",
         r"nginx :(\d+)", ports.get("web-port", ""), "web 端口"),
    ]

    for rel, pattern, expected, description in facts:
        if not expected:
            continue
        try:
            text = _read(root, rel)
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(f"{rel}: 无法读取：{exc}")
            continue
        match = re.search(pattern, text)
        if match is None:
            problems.append(f"{rel}: 找不到已登记的事实「{description}」（正则 {pattern}）")
            continue
        if match.group(1) != expected:
            problems.append(
                f"{rel}: {description} 写的是 {match.group(1)}，真相源是 {expected}"
            )

    if workflow_node and workflow_node != declared["node"]:
        problems.append(
            f".github/workflows/full-build.yml: node-version 是 {workflow_node}，版本表是 {declared['node']}"
        )

    return problems


# ────────────────────────────── 入口 ──────────────────────────────

def check_diagrams(root: Path = ROOT) -> list[str]:
    problems = check_references(root)
    references = root / "references"

    for name in DIAGRAMS:
        dot_path = references / f"{name}.dot"
        svg_path = references / f"{name}.svg"
        if not dot_path.is_file() or not svg_path.is_file():
            continue
        dot_rel = dot_path.relative_to(root).as_posix()
        svg_rel = svg_path.relative_to(root).as_posix()
        try:
            dot_model = parse_dot(dot_path.read_text(encoding="utf-8"), dot_rel)
        except (DiagramError, OSError, UnicodeDecodeError) as exc:
            problems.append(f"{dot_rel}: 解析失败：{exc}")
            continue
        try:
            svg_model = parse_svg(svg_path.read_text(encoding="utf-8"), svg_rel)
        except (DiagramError, OSError, UnicodeDecodeError) as exc:
            problems.append(f"{svg_rel}: 解析失败：{exc}")
            continue
        problems.extend(compare_models(dot_model, svg_model, dot_rel, svg_rel))

    problems.extend(check_facts(root))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_diagrams.py",
        description="检查架构图的 .dot / .svg / 文档引用与图内事实是否一致（离线、只读）",
    )
    parser.parse_args(argv)

    problems = check_diagrams(ROOT)
    if problems:
        print(f"==> 发现 {len(problems)} 处图漂移：", file=sys.stderr)
        for problem in problems:
            print("    " + problem, file=sys.stderr)
        return 1
    print("==> 通过：架构图与源文件、文档引用及图内事实一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

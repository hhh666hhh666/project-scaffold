from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

import check_diagrams as cd

FIXTURE_FILES = (
    "README.md",
    "SKILL.md",
    "references/ARCHITECTURE.md",
    "references/TECH-ARCHITECTURE.md",
    "references/TECH-STACK.md",
    "references/architecture.dot",
    "references/architecture.svg",
    "references/architecture-runtime.dot",
    "references/architecture-runtime.svg",
    "references/architecture-quality.dot",
    "references/architecture-quality.svg",
    "references/architecture-selftest.dot",
    "references/architecture-selftest.svg",
    ".github/workflows/selftest.yml",
    ".github/workflows/full-build.yml",
    "scripts/scaffold.py",
)


def clone_root(tmp: str) -> Path:
    root = Path(tmp)
    for rel in FIXTURE_FILES:
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, destination)
    return root


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"fixture 里找不到要替换的内容：{old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class DotParserTest(unittest.TestCase):
    def test_labels_escapes_and_hash_inside_quotes(self) -> None:
        model = cd.parse_dot(
            r'digraph g { a [label="第一行\n第二行", color="#ffffff"]; }'
        )
        self.assertEqual(model.nodes["a"], ("第一行", "第二行"))

    def test_implicit_nodes_rank_block_and_edge_chain(self) -> None:
        model = cd.parse_dot(
            """
            digraph g {
              subgraph cluster_x {
                label = "簇";
                a [label = "A"];
                { rank=same; a; b; }
              }
              a -> b -> c [label = "链路"];
            }
            """
        )
        self.assertEqual(model.clusters["cluster_x"], ("簇",))
        self.assertEqual(model.nodes["a"], ("A",))
        self.assertEqual(model.nodes["b"], ("b",))
        self.assertEqual(model.nodes["c"], ("c",))
        self.assertEqual(
            model.edges,
            [("a", "b", ("链路",)), ("b", "c", ("链路",))],
        )

    def test_nested_clusters_are_collected(self) -> None:
        model = cd.parse_dot(
            """
            digraph g {
              subgraph cluster_outer {
                label="外";
                subgraph cluster_inner { label="内"; n; }
              }
            }
            """
        )
        self.assertEqual(model.clusters["cluster_outer"], ("外",))
        self.assertEqual(model.clusters["cluster_inner"], ("内",))
        self.assertEqual(model.nodes["n"], ("n",))

    def test_unsupported_forms_raise_clear_errors(self) -> None:
        cases = {
            "strict digraph g { a; }": "strict",
            "graph g { a; }": "有向图",
            "digraph g { a:p -> b; }": "端口",
            "digraph g { a -> { b; c; } }": "子图作为边的端点",
            "digraph g { a [label=<b>] }": "不支持的字符",
            r'digraph g { a [label="\N"] }': "内置替换",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(cd.DiagramError) as error:
                    cd.parse_dot(text)
                self.assertIn(expected, str(error.exception))


class SvgParserTest(unittest.TestCase):
    def test_extracts_nodes_edges_and_clusters_without_nested_text(self) -> None:
        svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <g class="cluster">
    <title>cluster_x</title>
    <text>簇标题</text>
    <g class="node"><title>a</title><text>第一行</text><text>第二行</text></g>
  </g>
  <g class="edge"><title>a-&gt;b</title><text>标签</text></g>
</svg>"""
        model = cd.parse_svg(svg)
        self.assertEqual(model.clusters["cluster_x"], ("簇标题",))
        self.assertEqual(model.nodes["a"], ("第一行", "第二行"))
        self.assertEqual(model.edges, [("a", "b", ("标签",))])

    def test_broken_xml_is_reported(self) -> None:
        with self.assertRaises(cd.DiagramError) as error:
            cd.parse_svg("<svg><g>")
        self.assertIn("XML 解析失败", str(error.exception))


class RealRepositoryTest(unittest.TestCase):
    def test_real_repository_has_no_drift(self) -> None:
        self.assertEqual(cd.check_diagrams(ROOT), [])


class ReferenceTest(unittest.TestCase):
    def test_missing_svg_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            (root / "references/architecture-quality.svg").unlink()
            problems = cd.check_diagrams(root)
        self.assertTrue(any("缺少文件" in p and "architecture-quality" in p for p in problems), problems)

    def test_unregistered_diagram_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            (root / "references/architecture-extra.dot").write_text(
                "digraph g { a; }\n", encoding="utf-8"
            )
            problems = cd.check_diagrams(root)
        self.assertTrue(any("未登记的图" in p and "architecture-extra" in p for p in problems), problems)

    def test_svg_must_be_referenced_by_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            path = root / "references/TECH-ARCHITECTURE.md"
            edit(path, "![生成项目运行时架构](./architecture-runtime.svg)\n", "")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("没有被任何 Markdown" in p and "runtime" in p for p in problems), problems)

    def test_broken_image_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(
                root / "references/TECH-ARCHITECTURE.md",
                "./architecture-quality.svg",
                "./architecture-quality-missing.svg",
            )
            problems = cd.check_diagrams(root)
        self.assertTrue(any("指向不存在的文件" in p and "missing" in p for p in problems), problems)


class DriftTest(unittest.TestCase):
    def test_changed_dot_label_without_rerender_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/architecture-runtime.dot", "Vue SPA", "Vue 应用")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("节点 browser" in p and "不一致" in p for p in problems), problems)

    def test_changed_svg_text_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/architecture-runtime.svg", "Vue SPA", "Vue 应用")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("节点 browser" in p and "不一致" in p for p in problems), problems)

    def test_removed_edge_in_dot_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/architecture-quality.dot", '  dep -> ci [style=dashed, label="升级 PR 走普通 CI"];\n', "")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("多出边 dep -> ci" in p for p in problems), problems)


class FactTest(unittest.TestCase):
    def test_python_matrix_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / ".github/workflows/selftest.yml", "'3.11', '3.12', '3.13'", "'3.11', '3.12'")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("Python 版本矩阵" in p and "3.11 / 3.12" in p for p in problems), problems)

    def test_spring_boot_version_in_diagram_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/architecture-runtime.dot", "Spring Boot 3.5", "Spring Boot 3.4")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("Spring Boot 主次版本" in p and "3.4" in p for p in problems), problems)

    def test_port_default_in_script_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "scripts/scaffold.py", "default=8080", "default=8090")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("后端端口" in p and "8090" in p for p in problems), problems)

    def test_node_version_in_tech_doc_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = clone_root(tmp)
            edit(root / "references/TECH-ARCHITECTURE.md", "node:22-slim", "node:20-slim")
            problems = cd.check_diagrams(root)
        self.assertTrue(any("Node 主版本" in p and "20" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()

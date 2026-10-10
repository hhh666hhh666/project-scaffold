#!/usr/bin/env python3
"""project-scaffold 生成器：在目标目录里生成一个「有纪律、能跑、能测」的项目骨架。

用法：
    python scaffold.py                       # 无参数 → 逐项交互问答（回车即用默认）
    python scaffold.py --name my-app --out E:/tmp/my-app
    python scaffold.py --name my-app --out ./x --with-deploy --with-ops --with-testing
    python scaffold.py --name my-app --out ./x --dry-run

设计约束：
    * 仅用标准库。
    * 占位符语法 ${VAR}；**只有「全大写 + 下划线」的标识符会被替换**，
      其余 ${...}（Spring 占位符、bash 变量、Maven 属性、compose 变量）一律原样保留。
    * 文本一律 UTF-8 + LF 写入，避免 Windows 上产生 CRLF。
    * 产物只落在 --out 指定的目录里。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"

# 只有「全大写 + 下划线」的 ${XXX} 会被替换。
# 这样 Spring 的 ${myapp.jwt.secret}、bash 的 ${1:-}、Maven 的 ${java.version}
# 都不会被误伤——它们要么含小写，要么含 : / . / [ 等字符。
VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PACKAGE_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$")

# 模板子目录 → 目标子目录（相对 --out）。None 表示该段直接落到根目录。
# (源目录名, 目标目录, 需要的开关；None = 总是生成)
DIR_PLAN = [
    ("root", ".", None),
    ("rules", ".codebuddy/rules", None),
    ("commands", ".codebuddy/commands", None),
    ("docs", "docs", None),
    ("backend", "backend", None),
    ("frontend", "frontend", None),
    ("ci", ".github/workflows", None),
    ("docker", ".", None),
    ("scripts", "scripts", None),
    ("testing", "docs/testing", "with_testing"),
    ("ops", "docs/operations", "with_ops"),
    ("deploy", ".", "with_deploy"),
]

# 生成后要保证存在的目录（空目录补 .gitkeep，免得 git 不跟踪）
EMPTY_DIRS = [
    "docs/adr",
    "docs/design",
    "docs/development",
    "docs/operations",
    "docs/requirements",
    "docs/testing",
    "docs/todo/archive",
    "docs/worklog",
]

SCRIPT_NAMES = {
    "LINK_CHECK_SCRIPT": "check-doc-links.sh",
    "TODO_ARCHIVE_SCRIPT": "check-todo-archive.sh",
    "MODULE_TEST_SCRIPT": "check-module-tests.sh",
    "VERSION_SCRIPT": "check-version.sh",
}


# ────────────────────────────── 变量表 ──────────────────────────────

def pascal(name: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[-_.]+", name) if p)


def build_context(
    project_name: str,
    package: str,
    version: str,
    backend_port: int,
    frontend_port: int,
    web_port: int,
    db_name: str,
) -> dict[str, str]:
    app_class = pascal(project_name)
    app_prefix = re.sub(r"[^a-z0-9]", "", project_name.lower()) or "app"
    env = app_prefix.upper()

    ctx: dict[str, str] = {
        "PROJECT_NAME": project_name,
        "APP_CLASS": app_class,
        "APP_PREFIX": app_prefix,
        "APP_ENV_PREFIX": env,
        "PACKAGE": package,
        "PACKAGE_PATH": package.replace(".", "/"),
        "VERSION": version,
        "BACKEND_PORT": str(backend_port),
        "FRONTEND_PORT": str(frontend_port),
        "WEB_PORT": str(web_port),
        "DB_NAME": db_name,
    }
    ctx.update(SCRIPT_NAMES)

    # 复合变量：值本身含 ${...}，用于「生成物里必须保留一个 ${} 包裹」的场合
    # （Spring 的 @Value / yml 占位符 / compose 断言）。值不会被二次替换。
    default_secret = f"{app_prefix}-default-jwt-secret-please-replace-in-production-0123456789abcdef"
    ctx["JWT_DEFAULT_SECRET"] = default_secret
    ctx["CONFIG_VERSION_ANNOTATION"] = "${" + app_prefix + ".version:dev}"
    ctx["CORS_ANNOTATION"] = "${" + app_prefix + ".cors.allowed-origins:}"
    ctx["JWT_SECRET_ANNOTATION"] = "${" + env + "_JWT_SECRET}"
    ctx["JWT_EXPIRE_ANNOTATION"] = "${" + env + "_JWT_EXPIRE_DAYS:7}"
    ctx["JWT_SECRET_YAML"] = "${" + env + "_JWT_SECRET:" + default_secret + "}"
    ctx["APP_VERSION_YAML"] = "${" + env + "_VERSION:dev}"
    ctx["CORS_YAML"] = "${" + env + "_CORS_ALLOWED_ORIGINS:}"
    ctx["JWT_EXPIRE_YAML"] = "${" + env + "_JWT_EXPIRE_DAYS:7}"
    ctx["JWT_SECRET_ASSERT"] = "${" + env + "_JWT_SECRET:?请在 .env 里设置 " + env + "_JWT_SECRET}"
    ctx["JWT_EXPIRE_COMPOSE"] = "${" + env + "_JWT_EXPIRE_DAYS:-7}"
    ctx["CORS_COMPOSE"] = "${" + env + "_CORS_ALLOWED_ORIGINS:-}"
    return ctx


def render(text: str, ctx: dict[str, str]) -> str:
    return VAR_RE.sub(lambda m: ctx.get(m.group(1), m.group(0)), text)


# ────────────────────────────── 交互问答 ──────────────────────────────

def ask(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def ask_bool(prompt: str, default: bool) -> bool:
    hint = "y/N" if not default else "Y/n"
    raw = input(f"{prompt} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "是", "true", "1")


def interactive() -> argparse.Namespace:
    print("==> 逐项问答，回车即用默认值\n")
    while True:
        name = ask("项目名（kebab-case，如 my-app）", "my-app")
        if NAME_RE.match(name):
            break
        print("    ⚠️ 只能小写字母 / 数字 / 连字符，且不能以数字或连字符开头")
    default_pkg = "com.example." + re.sub(r"[^a-z0-9]", "", name.lower())
    while True:
        package = ask("Java 包名", default_pkg)
        if PACKAGE_RE.match(package):
            break
        print("    ⚠️ 形如 com.example.myapp")
    out = ask("输出目录", f"./{name}")
    version = ask("初始版本", "0.1.0")
    backend_port = ask("后端端口", "8080")
    frontend_port = ask("前端 dev 端口", "5173")
    db_name = ask("数据库名", re.sub(r"[^a-z0-9_]", "_", name.lower()))
    modules = ask("额外业务模块（逗号分隔，可留空；example 样例模块总会生成）", "")
    print()
    with_deploy = ask_bool("生成部署章节（release.yml / compose.prod / 服务器脚本）", False)
    with_ops = ask_bool("生成运维章节（docs/operations/内存策略.md）", False)
    with_testing = ask_bool("生成测试规范章节（docs/testing/）", False)

    return argparse.Namespace(
        name=name, package=package, out=out, version=version,
        backend_port=int(backend_port), frontend_port=int(frontend_port),
        web_port=8081, db_name=db_name, modules=modules,
        with_deploy=with_deploy, with_ops=with_ops, with_testing=with_testing,
        force=False, dry_run=False,
    )


# ────────────────────────────── 生成 ──────────────────────────────

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def make_module_skeleton(out: Path, ctx: dict[str, str], modules: list[str]) -> list[str]:
    """额外业务模块：只建空包骨架（含 .gitkeep），不预置代码。"""
    created: list[str] = []
    base = out / "backend" / "src" / "main" / "java" / ctx["PACKAGE_PATH"] / "module"
    test_base = out / "backend" / "src" / "test" / "java" / ctx["PACKAGE_PATH"] / "module"
    for mod in modules:
        for sub in ("controller", "dto", "entity", "mapper", "service", "vo"):
            d = base / mod / sub
            d.mkdir(parents=True, exist_ok=True)
            keep = d / ".gitkeep"
            if not keep.exists():
                write_text(keep, "")
                created.append(str(d.relative_to(out)).replace("\\", "/") + "/.gitkeep")
        t = test_base / mod / "service"
        t.mkdir(parents=True, exist_ok=True)
        keep = t / ".gitkeep"
        if not keep.exists():
            write_text(keep, "")
            created.append(str(t.relative_to(out)).replace("\\", "/") + "/.gitkeep")
    return created


def ensure_empty_dirs(out: Path) -> list[str]:
    created: list[str] = []
    for rel in EMPTY_DIRS:
        d = out / rel
        d.mkdir(parents=True, exist_ok=True)
        if not any(d.iterdir()):
            keep = d / ".gitkeep"
            if not keep.exists():
                write_text(keep, "")
                created.append(rel + "/.gitkeep")
    return created


def generate(args: argparse.Namespace) -> int:
    ctx = build_context(
        args.name, args.package, args.version,
        args.backend_port, args.frontend_port, args.web_port, args.db_name,
    )
    out = Path(args.out).resolve()
    extra_modules = [m.strip() for m in (args.modules or "").split(",") if m.strip()]

    flags = {"with_deploy": args.with_deploy, "with_ops": args.with_ops, "with_testing": args.with_testing}

    planned: list[tuple[Path, Path]] = []   # (源绝对, 目标绝对)
    for src_name, target_name, flag in DIR_PLAN:
        if flag and not flags[flag]:
            continue
        src_root = TEMPLATES / src_name
        if not src_root.is_dir():
            print(f"    ⚠️ 模板目录缺失：{src_root}", file=sys.stderr)
            continue
        dst_root = out if target_name == "." else out / target_name
        for path in sorted(src_root.rglob("*")):
            if path.is_dir():
                continue
            rel = render(path.relative_to(src_root).as_posix(), ctx)
            planned.append((path, dst_root / rel))

    # 幂等保护
    existing = [dst for _, dst in planned if dst.exists()]
    if out.exists() and any(out.iterdir()) and not args.force and not args.dry_run:
        print(f"==> 目标目录非空：{out}\n    加 --force 才会覆盖模板产物（不会删除你的其他文件）。", file=sys.stderr)
        return 2
    if existing and not args.force and not args.dry_run:
        print(f"==> 有 {len(existing)} 个文件已存在（如 {existing[0]}），加 --force 覆盖。", file=sys.stderr)
        return 2

    print(f"==> 项目：{ctx['PROJECT_NAME']}  包：{ctx['PACKAGE']}  输出：{out}")
    print(f"==> 可选章节：deploy={args.with_deploy} ops={args.with_ops} testing={args.with_testing}")
    if args.dry_run:
        print("\n==> dry-run：以下文件将被创建（不落盘）")
        for _, dst in planned:
            print("    " + str(dst.resolve().relative_to(out)).replace("\\", "/"))
        print(f"\n    共 {len(planned)} 个文件")
        return 0

    written: list[str] = []
    for src, dst in planned:
        try:
            content = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"    ⚠️ 跳过非文本文件：{src}", file=sys.stderr)
            continue
        write_text(dst, render(content, ctx))
        written.append(str(dst.resolve().relative_to(out)).replace("\\", "/"))

    written += ensure_empty_dirs(out)
    if extra_modules:
        written += make_module_skeleton(out, ctx, extra_modules)

    print(f"\n==> 已生成 {len(written)} 个文件 / 占位")
    if extra_modules:
        print(f"==> 额外模块骨架：{', '.join(extra_modules)}（只有目录，代码自己写）")

    print(
        "\n==> 下一步（本地验证）\n"
        f"    cd {out}\n"
        "    docker compose -f docker-compose.dev.yml up -d          # 起数据库\n"
        "    # 后端\n"
        "    cd backend && mvn -B -ntp test\n"
        "    # 前端\n"
        "    cd frontend && npm install && npm run typecheck\n"
        "\n==> 然后进初始化：按 skill 里的初始化剧本（references/POST-SCAFFOLD.md）\n"
        "    从「入库基线」一路走到「CI 首绿」；完成后提示用户发 @skill:grill-with-docs 接需求打磨。"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scaffold.py",
        description="生成一个带文档体系与技术架构的新项目骨架",
    )
    parser.add_argument("--name", help="项目名（kebab-case，如 my-app）")
    parser.add_argument("--package", help="Java 包名（如 com.example.myapp）")
    parser.add_argument("--out", help="输出目录（默认 ./<项目名>）")
    parser.add_argument("--version", default="0.1.0", help="初始版本号（默认 0.1.0）")
    parser.add_argument("--backend-port", type=int, default=8080, help="后端端口（默认 8080）")
    parser.add_argument("--frontend-port", type=int, default=5173, help="前端 dev 端口（默认 5173）")
    parser.add_argument("--web-port", type=int, default=8081, help="prod 里 web 容器映射到宿主的端口（默认 8081）")
    parser.add_argument("--db", dest="db_name", help="数据库名（默认由项目名派生）")
    parser.add_argument("--modules", default="", help="额外业务模块（逗号分隔），只建空包骨架")
    parser.add_argument("--with-deploy", action="store_true", help="生成部署章节")
    parser.add_argument("--with-ops", action="store_true", help="生成运维章节（内存策略）")
    parser.add_argument("--with-testing", action="store_true", help="生成测试规范章节")
    parser.add_argument("--force", action="store_true", help="目标已存在时覆盖模板产物")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要创建的文件，不落盘")

    args = parser.parse_args(argv)

    if args.name is None:
        # 命令行给了别的参数却没给 --name → 报错；完全不带参数才进交互问答。
        if len(sys.argv) > 1:
            parser.error("给了参数但缺 --name；不带任何参数才会进交互问答")
        args = interactive()

    if not NAME_RE.match(args.name):
        parser.error("--name 必须是 kebab-case：小写字母 / 数字 / 连字符，且不能以数字或连字符开头")
    if args.package is None:
        args.package = "com.example." + re.sub(r"[^a-z0-9]", "", args.name.lower())
    if not PACKAGE_RE.match(args.package):
        parser.error("--package 形如 com.example.myapp")
    if args.out is None:
        args.out = f"./{args.name}"
    if not args.db_name:
        args.db_name = re.sub(r"[^a-z0-9_]", "_", args.name.lower())

    return generate(args)


if __name__ == "__main__":
    sys.exit(main())

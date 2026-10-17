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
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATES = ROOT / "templates"

# 生成记录：默认写入项目根，建议随项目入库；记录的是「最近一次完整生成」。
SCAFFOLD_RECORD_NAME = ".scaffold.json"
SCAFFOLD_RECORD_SCHEMA = 1
GENERATOR_NAME = "project-scaffold"
# dirty 只看生成器自身的输入，不因 README / 测试 / 业务文件变化而误报。
SOURCE_PATHS = ("scripts/scaffold.py", "templates")

# 只有「全大写 + 下划线」的 ${XXX} 会被替换。
# 这样 Spring 的 ${myapp.jwt.secret}、bash 的 ${1:-}、Maven 的 ${java.version}
# 都不会被误伤——它们要么含小写，要么含 : / . / [ 等字符。
VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PACKAGE_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$")
# 业务模块名直接当 Java 包段与目录名用：只许小写字母数字，挡住 ../、大写、连字符
MODULE_RE = re.compile(r"^[a-z][a-z0-9]*$")

# 能单独当包段的 Java 关键字 / 字面量（javac 会拒绝 com.example.class 这种包名）
JAVA_KEYWORDS = frozenset("""
    abstract assert boolean break byte case catch char class const continue default do
    double else enum extends false final finally float for goto if implements import
    instanceof int interface long native new null package private protected public return
    short static strictfp super switch synchronized this throw throws transient true try
    void volatile while _
""".split())

# 模板里「运行时自己定义」的全大写变量（shell 赋值 / for 变量、yml 与 .env 的键、Dockerfile ARG/ENV）。
# 这些名字一旦与变量表撞名，生成时就会被静默替换成表里的值——生成前必须拦下。
RUNTIME_SUFFIXES = (".sh", ".yml", ".yaml", ".example")
RUNTIME_DEF_RE = re.compile(
    r"^\s*(?:(?:export|local|readonly|declare)\s+|for\s+|(?:ARG|ENV)\s+|-\s+)?"
    r"([A-Z][A-Z0-9_]*)(?:=|:\s|:$|\s+in\b)",
    re.MULTILINE,
)

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

# 额外业务模块的空包骨架（与 example 模块的分层一致）
MODULE_SUBDIRS = ("controller", "dto", "entity", "mapper", "service", "vo")

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
    # 注解读 yml 的配置键而不是环境变量本身：兜底默认值只写在 yml 一处，
    # 没设环境变量时才能落到默认值（再由 JwtUtil 换成随机密钥），而不是启动即失败。
    ctx["JWT_SECRET_ANNOTATION"] = "${" + app_prefix + ".jwt.secret}"
    ctx["JWT_EXPIRE_ANNOTATION"] = "${" + app_prefix + ".jwt.expire-days:7}"
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


# ────────────────────────────── 生成记录 ──────────────────────────────

def _git_run(args: list[str], root: Path, timeout: int = 5) -> str | None:
    """只读查询；Git 不存在、超时或失败都返回 None，不影响正常生成。"""
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def detect_generator_source(root: Path = ROOT) -> dict:
    """识别脚手架自身的提交；只认「仓库根恰好是脚手架根」，避免误记外层仓库。"""
    unknown = {"commit": None, "dirty": None, "status": "unknown"}
    top = _git_run(["rev-parse", "--show-toplevel"], root)
    if not top:
        return unknown
    try:
        if Path(top).resolve() != root.resolve():
            return unknown
    except OSError:
        return unknown
    commit = _git_run(["rev-parse", "HEAD"], root)
    if not commit or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return unknown
    # --no-optional-locks：不刷新索引，尽量保持只读。
    status = _git_run(
        ["--no-optional-locks", "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS],
        root,
    )
    return {"commit": commit, "dirty": None if status is None else bool(status), "status": "git"}


def source_summary(source: dict) -> str:
    if source.get("status") != "git":
        return "未知（不是独立的脚手架 Git 仓库，或查询失败）"
    text = str(source.get("commit") or "")[:7]
    if source.get("dirty") is True:
        return text + "（生成器或模板有本地改动）"
    if source.get("dirty") is None:
        return text + "（本地改动状态未知）"
    return text + "（生成器与模板无本地改动）"


def build_scaffold_record(ctx: dict[str, str], modules: list[str],
                          args: argparse.Namespace, source: dict | None = None) -> dict:
    """字段白名单：只存项目参数与脚手架来源，不存路径、时间、环境或凭据。"""
    return {
        "schema_version": SCAFFOLD_RECORD_SCHEMA,
        "generator": {
            "name": GENERATOR_NAME,
            "source": dict(source if source is not None else detect_generator_source()),
        },
        "project": {
            "name": ctx["PROJECT_NAME"],
            "package": ctx["PACKAGE"],
            "initial_version": ctx["VERSION"],
            "database": ctx["DB_NAME"],
            "ports": {
                "backend": int(ctx["BACKEND_PORT"]),
                "frontend": int(ctx["FRONTEND_PORT"]),
                "web": int(ctx["WEB_PORT"]),
            },
            "modules": list(modules),
            "switches": {
                "deploy": bool(args.with_deploy),
                "ops": bool(args.with_ops),
                "testing": bool(args.with_testing),
            },
        },
    }


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重复的 JSON 键：{key}")
        result[key] = value
    return result


def existing_record_problem(path: Path) -> str | None:
    """已有记录必须是本生成器能理解的格式；否则拒绝覆盖，哪怕带 --force。"""
    if path.is_symlink():
        return f"{path} 是符号链接，拒绝覆盖"
    if not path.exists():
        return None
    if not path.is_file():
        return f"{path} 不是普通文件，拒绝覆盖"
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return f"{path} 无法解析（{exc}）；请先备份并人工处理"
    if not isinstance(data, dict) or data.get("schema_version") != SCAFFOLD_RECORD_SCHEMA:
        return f"{path} 不是受支持的脚手架记录（schema_version 需为 {SCAFFOLD_RECORD_SCHEMA}）"
    generator = data.get("generator")
    if not isinstance(generator, dict) or generator.get("name") != GENERATOR_NAME:
        return f"{path} 缺少 {GENERATOR_NAME} 标识，拒绝覆盖"
    return None


def write_scaffold_record(path: Path, record: dict) -> None:
    """先写同目录临时文件，再原子替换，失败不破坏已有记录。"""
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        write_text(tmp, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        os.chmod(tmp, 0o644)   # mkstemp 默认 0600；记录是项目文件，按普通文本文件发布
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


# ────────────────────────────── 交互问答 ──────────────────────────────

def ask(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def valid_port(raw: str) -> int | None:
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= 65535 else None


def ask_port(prompt: str, default: str) -> int:
    while True:
        port = valid_port(ask(prompt, default))
        if port is not None:
            return port
        print("    ⚠️ 端口必须是 1-65535 的整数")


def parse_modules(raw: str) -> tuple[list[str], list[str]]:
    """拆分 --modules：返回 (去重后的合法模块, 非法项)。example 总会生成，传了也忽略。"""
    good: list[str] = []
    bad: list[str] = []
    for m in (x.strip() for x in (raw or "").split(",")):
        if not m or m == "example" or m in good:
            continue
        if MODULE_RE.match(m) and m not in JAVA_KEYWORDS:
            good.append(m)
        else:
            bad.append(m)
    return good, bad


def package_error(package: str) -> str | None:
    if not PACKAGE_RE.match(package):
        return "形如 com.example.myapp"
    kw = [seg for seg in package.split(".") if seg in JAVA_KEYWORDS]
    if kw:
        return f"包段不能是 Java 关键字：{', '.join(kw)}"
    return None


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
        err = package_error(package)
        if not err:
            break
        print(f"    ⚠️ {err}")
    out = ask("输出目录", f"./{name}")
    version = ask("初始版本", "0.1.0")
    backend_port = ask_port("后端端口", "8080")
    frontend_port = ask_port("前端 dev 端口", "5173")
    db_name = ask("数据库名", re.sub(r"[^a-z0-9_]", "_", name.lower()))
    while True:
        modules = ask("额外业务模块（逗号分隔，可留空；example 样例模块总会生成）", "")
        _, bad = parse_modules(modules)
        if not bad:
            break
        print(f"    ⚠️ 模块名只能是小写字母开头的小写字母 / 数字，且不能是 Java 关键字：{', '.join(bad)}")
    print()
    with_deploy = ask_bool("生成部署章节（release.yml / compose.prod / 服务器脚本）", False)
    with_ops = ask_bool("生成运维章节（docs/operations/内存策略.md）", False)
    with_testing = ask_bool("生成测试规范章节（docs/testing/）", False)

    return argparse.Namespace(
        name=name, package=package, out=out, version=version,
        backend_port=backend_port, frontend_port=frontend_port,
        web_port=8081, db_name=db_name, modules=modules,
        with_deploy=with_deploy, with_ops=with_ops, with_testing=with_testing,
        force=False, dry_run=False, json=False,
    )


# ────────────────────────────── 生成 ──────────────────────────────

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def rel_posix(path: Path, out: Path) -> str:
    return path.relative_to(out).as_posix()


def plan_keepfiles(out: Path, ctx: dict[str, str], modules: list[str],
                   planned_dsts: list[Path]) -> list[Path]:
    """算出要补 .gitkeep 的位置：恒定目录 + 额外模块的空包骨架。

    只算不写，好让 dry-run 与真实生成打印同一份清单。
    已经会有模板文件落进去、或者磁盘上本来就有内容的目录，不补。
    """
    dirs = [out / rel for rel in EMPTY_DIRS]
    main_base = out / "backend" / "src" / "main" / "java" / ctx["PACKAGE_PATH"] / "module"
    test_base = out / "backend" / "src" / "test" / "java" / ctx["PACKAGE_PATH"] / "module"
    for mod in modules:
        dirs += [main_base / mod / sub for sub in MODULE_SUBDIRS]
        dirs.append(test_base / mod / "service")

    keeps: list[Path] = []
    for d in dirs:
        if any(dst.is_relative_to(d) for dst in planned_dsts):
            continue
        if d.is_dir() and any(d.iterdir()):
            continue
        keeps.append(d / ".gitkeep")
    return keeps


def find_collisions(ctx: dict[str, str]) -> list[str]:
    """扫全部模板（不论开关），找「运行时自己定义、却与变量表同名」的全大写变量。"""
    hits: list[str] = []
    for path in sorted(TEMPLATES.rglob("*")):
        if not path.is_file():
            continue
        # 按渲染后的文件名判断类型：守卫脚本在模板里叫 ${LINK_CHECK_SCRIPT}，渲染后才有 .sh
        name = render(path.name, ctx)
        if not (name.endswith(RUNTIME_SUFFIXES) or name == "Dockerfile"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in RUNTIME_DEF_RE.finditer(text):
            if m.group(1) in ctx:
                line = text.count("\n", 0, m.start(1)) + 1
                hits.append(f"{path.relative_to(TEMPLATES).as_posix()}:{line}  {m.group(1)}")
    return hits


def generate(args: argparse.Namespace) -> int:
    ctx = build_context(
        args.name, args.package, args.version,
        args.backend_port, args.frontend_port, args.web_port, args.db_name,
    )
    out = Path(args.out).resolve()
    extra_modules, _ = parse_modules(args.modules)   # main() 已拦下非法项

    # 模板自检：运行时变量与变量表撞名 = 模板 bug，生成出来的东西会被静默改坏
    collisions = find_collisions(ctx)
    if collisions:
        print("==> 模板自检失败：以下运行时变量与变量表同名，生成时会被误替换：", file=sys.stderr)
        for hit in collisions:
            print("    " + hit, file=sys.stderr)
        print("    改掉模板里的变量名（或变量表里的名字），见 references/VARIABLES.md。", file=sys.stderr)
        return 2

    flags = {"with_deploy": args.with_deploy, "with_ops": args.with_ops, "with_testing": args.with_testing}

    planned: list[tuple[Path, Path]] = []   # (源绝对, 目标绝对)
    for src_name, target_name, flag in DIR_PLAN:
        if flag and not flags[flag]:
            continue
        src_root = TEMPLATES / src_name
        if not src_root.is_dir():
            print(f"==> 模板目录缺失：{src_root}；本次生成未开始", file=sys.stderr)
            return 2
        dst_root = out if target_name == "." else out / target_name
        for path in sorted(src_root.rglob("*")):
            if path.is_dir():
                continue
            # 写入前先验一遍编码：中途因坏模板停下会留下半成品，不如提前失败。
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"==> 模板不是 UTF-8 文本：{path}；本次生成未开始", file=sys.stderr)
                return 2
            rel = render(path.relative_to(src_root).as_posix(), ctx)
            planned.append((path, dst_root / rel))

    keeps = plan_keepfiles(out, ctx, extra_modules, [dst for _, dst in planned])

    record_path = out / SCAFFOLD_RECORD_NAME
    if any(dst == record_path for _, dst in planned):
        print(f"==> 模板产物与生成记录路径冲突：{SCAFFOLD_RECORD_NAME}", file=sys.stderr)
        return 2
    record_error = existing_record_problem(record_path)
    if record_error:
        print(f"==> 已有生成记录不可用：{record_error}", file=sys.stderr)
        return 2

    # 幂等保护：目录非空就拒绝（模板文件已存在必然意味着目录非空，所以一条判断就够）
    if out.exists() and not out.is_dir():
        print(f"==> 输出路径不是目录：{out}", file=sys.stderr)
        return 2
    if out.exists() and any(out.iterdir()) and not args.force and not args.dry_run:
        existing = sum(1 for _, dst in planned if dst.exists())
        print(f"==> 目标目录非空：{out}（其中 {existing} 个模板产物已存在）\n"
              "    加 --force 才会覆盖模板产物（不会删除你的其他文件）。", file=sys.stderr)
        return 2

    if not out.exists():
        target_code, target_state = "missing", "不存在（将新建）"
        existing = 0
    elif any(out.iterdir()):
        existing = sum(1 for _, dst in planned if dst.exists())
        target_code = "non_empty"
        target_state = f"非空（{existing} 个模板产物已存在，{'将覆盖' if args.force else '正式执行会拒绝'}）"
    else:
        existing = 0
        target_code, target_state = "empty", "空目录（将写入）"

    source = detect_generator_source()
    record = build_scaffold_record(ctx, extra_modules, args, source)

    if args.dry_run and args.json:
        files = ([rel_posix(dst, out) for _, dst in planned]
                 + [rel_posix(keep, out) for keep in keeps]
                 + [SCAFFOLD_RECORD_NAME])
        plan = {
            "project": ctx["PROJECT_NAME"],
            "package": ctx["PACKAGE"],
            "out": str(out),
            "version": ctx["VERSION"],
            "database": ctx["DB_NAME"],
            "ports": {
                "backend": int(ctx["BACKEND_PORT"]),
                "frontend": int(ctx["FRONTEND_PORT"]),
                "web": int(ctx["WEB_PORT"]),
            },
            "modules": extra_modules,
            "switches": {
                "deploy": args.with_deploy,
                "ops": args.with_ops,
                "testing": args.with_testing,
            },
            "force": args.force,
            "dry_run": True,
            "target": {
                "exists": out.exists(),
                "state": target_code,
                "existing_template_files": existing,
                "would_refuse": target_code == "non_empty" and not args.force,
            },
            "file_count": len(files),
            "files": files,
            "scaffold_record": {
                "path": SCAFFOLD_RECORD_NAME,
                "content": record,
            },
        }
        # 机器可读输出固定用 UTF-8：Windows 上重定向到文件时默认走本地编码（GBK），
        # 中文路径会让下游按 UTF-8 解析失败。StringIO 等无 reconfigure 的流跳过即可。
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    print(f"==> 项目：{ctx['PROJECT_NAME']}  包：{ctx['PACKAGE']}  输出：{out}")
    print(f"==> 版本：{ctx['VERSION']}  数据库：{ctx['DB_NAME']}")
    print(f"==> 端口：backend={ctx['BACKEND_PORT']} frontend={ctx['FRONTEND_PORT']} web={ctx['WEB_PORT']}")
    print(f"==> 额外模块：{', '.join(extra_modules) if extra_modules else '无'}")
    print(f"==> 可选章节：deploy={args.with_deploy} ops={args.with_ops} testing={args.with_testing}")
    print(f"==> 目标状态：{target_state}  force={args.force}")
    print(f"==> 脚手架来源：{source_summary(source)}")
    if args.dry_run:
        print("\n==> dry-run：以下文件将被创建或覆盖（不落盘）")
        for dst in [dst for _, dst in planned] + keeps + [record_path]:
            print("    " + rel_posix(dst, out))
        print(f"\n    共 {len(planned) + len(keeps) + 1} 个文件 / 占位")
        return 0

    written: list[str] = []
    try:
        for src, dst in planned:
            content = src.read_text(encoding="utf-8")
            write_text(dst, render(content, ctx))
            written.append(rel_posix(dst, out))
        for keep in keeps:
            write_text(keep, "")
            written.append(rel_posix(keep, out))
        # 记录最后发布：中途失败时，已有的旧记录不会被提前改掉。
        write_scaffold_record(record_path, record)
        written.append(SCAFFOLD_RECORD_NAME)
    except OSError as exc:
        print(f"\n==> 写入失败：{exc}", file=sys.stderr)
        print("    本次生成未完成；可能留下部分文件，已有 .scaffold.json 不会被更新。", file=sys.stderr)
        return 2

    print(f"\n==> 已生成 {len(written)} 个文件 / 占位")
    if extra_modules:
        print(f"==> 额外模块骨架：{', '.join(extra_modules)}（只有目录，代码自己写）")

    print(
        "\n==> 下一步（本地验证）\n"
        f"    cd {out}\n"
        "    # 基础门禁（不需要 Docker 或数据库）\n"
        "    cd backend && mvn -B -ntp test\n"
        "    cd frontend && npm install && npm run typecheck\n"
        "    # 有数据库时再按 references/POST-SCAFFOLD.md 选择 Docker MySQL 或专用外部 MySQL\n"
        "\n==> 然后进初始化：按 skill 里的初始化剧本（references/POST-SCAFFOLD.md）\n"
        "    先选择 Docker MySQL、专用外部 MySQL，或暂时只做不依赖数据库的门禁；\n"
        "    没有 MySQL 时不要宣称本地全链路已跑通，获得数据库后再补真实联通验收。\n"
        "    完成后检查配套 skill（缺了先问再拉），再提示使用者手动触发 grill-with-docs。"
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
    parser.add_argument("--json", action="store_true", help="与 --dry-run 配合，输出机器可读的 JSON 计划")

    args = parser.parse_args(argv)

    if args.name is None:
        # 命令行给了别的参数却没给 --name → 报错；完全不带参数才进交互问答。
        if len(sys.argv) > 1:
            parser.error("给了参数但缺 --name；不带任何参数才会进交互问答")
        args = interactive()

    if args.json and not args.dry_run:
        parser.error("--json 只能与 --dry-run 一起使用（JSON 是生成前的计划预览，不是生成产物）")
    if not NAME_RE.match(args.name):
        parser.error("--name 必须是 kebab-case：小写字母 / 数字 / 连字符，且不能以数字或连字符开头")
    if args.package is None:
        args.package = "com.example." + re.sub(r"[^a-z0-9]", "", args.name.lower())
    err = package_error(args.package)
    if err:
        parser.error(f"--package {err}")
    for opt in ("backend_port", "frontend_port", "web_port"):
        if valid_port(str(getattr(args, opt))) is None:
            parser.error(f"--{opt.replace('_', '-')} 必须是 1-65535 的整数")
    _, bad = parse_modules(args.modules)
    if bad:
        parser.error(f"--modules 里有非法模块名（只能小写字母开头的小写字母 / 数字，且不能是 Java 关键字）：{', '.join(bad)}")
    if args.out is None:
        args.out = f"./{args.name}"
    if not args.db_name:
        args.db_name = re.sub(r"[^a-z0-9_]", "_", args.name.lower())

    return generate(args)


if __name__ == "__main__":
    sys.exit(main())

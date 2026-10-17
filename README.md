# project-scaffold

> 把一个空目录变成一个**有纪律、能跑、能测**的项目，并把它一路带到 CI 首绿。

这是一个 AI 编码工具（WorkBuddy / Claude Code 等）的 **Skill**，不是普通的代码模板仓库。
它由三部分组成：**一套模板文件** + **一个生成脚本** + **一份初始化剧本**。

模板只是骨架。真正有价值的是另外两样：

- **文档体系里的每一条纪律，都对应一次真实的翻车**——不是凭空想出来的规范；
- **四条机械守卫让「不做就过不去」**——纪律靠脚本落地，不靠自觉。

---

## 它解决什么

| 常见状况 | 这个项目怎么处理 |
|---|---|
| AI 生成的项目「跑不起来」，前后端没真正打通 | 首页那行字**必须来自后端接口**，这是「通了」的肉眼判据，不是装饰 |
| 文档写完就烂，改了代码没人同步 | 改代码 = 改文档，写进 `.codebuddy/rules/`，每次会话自动加载 |
| 未决事项散落在聊天记录里，下次开会话全丢 | 未决事项必须落 `docs/todo/` 成为文件，否则当次回复不算完 |
| 文档互相引用，文件一移动全是死链 | `check-doc-links.sh` 守着，断了过不去 |
| 待办解决完还留在 `docs/todo/` 里发霉 | `check-todo-archive.sh` 逼着 `git mv` 到 `archive/` |
| 版本号散落在 5 个文件里，发版时总漏改一处 | `check-version.sh` 比对 tag 与所有版本字符串 |
| 新模块写完没有测试，也没人发现 | `check-module-tests.sh` 检查每个业务模块有没有对应测试 |
| 骨架生成完就停拍，项目卡在「能编译但没上线」 | 初始化剧本六阶段，一路带到 **CI 首绿** |

---

## 快速开始

### 安装

把整个目录复制到 Skill 目录即可：

```bash
# WorkBuddy / Claude Code（用户级）
cp -r project-scaffold ~/.workbuddy/skills/

# 或作为项目级 skill
cp -r project-scaffold .workbuddy/skills/
```

安装后对话里说一句「**我要做一个 xx 系统**」就会触发。

### 用法

```bash
# 交互问答（不带参数）
python scripts/scaffold.py

# 参数模式
python scripts/scaffold.py --name my-app \
    --package com.example.myapp \
    --out E:/code/my-app
```

脚本**只用 Python 标准库**，Python 3.11+ 即可，无任何第三方依赖。

⚠️ **产物只落在 `--out` 指定的目录**，绝不在当前仓库根生成。

### 三个开关（互相独立，默认都不开）

| 开关 | 生成什么 | 什么时候开 |
|---|---|---|
| `--with-deploy` | `release.yml`、`docker-compose.prod.yml`、`scripts/server-*.sh`、`deploy/` 模板 | 确定要上线到服务器时 |
| `--with-ops` | `docs/operations/内存策略.md`（预设 2C2G 的算法与示例） | 跑在小机器上、或要共用服务器时 |
| `--with-testing` | `docs/testing/` 分层规范与同步纪律 | 准备认真写测试时 |

### 常用参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--name` | （必填） | 项目名，kebab-case，同时是 npm 包名 / compose 项目名 / 容器名前缀 |
| `--package` | `com.example.<name 去掉连字符>` | Java 包名（如 `demo-app` → `com.example.demoapp`） |
| `--out` | `./<name>` | 输出目录 |
| `--version` | `0.1.0` | 初始版本号 |
| `--backend-port` / `--frontend-port` / `--web-port` | `8080` / `5173` / `8081` | 端口 |
| `--db` | 由项目名派生 | 数据库名 |
| `--modules` | 无 | 额外业务模块（逗号分隔），只建空包骨架 |
| `--dry-run` | 关 | 只打印将要创建的文件，不落盘 |
| `--force` | 关 | 目标已存在时覆盖模板产物（不删其他文件） |

---

## 生成什么

| 模板目录 | 落到新项目 | 开关 |
|---|---|---|
| `root/` | 仓库根（`README.md` / `AGENTS.md` / `CONTEXT.md` / `PRODUCT.md` / `DESIGN.md` / `CHANGELOG.md` / `.env.example` / `.gitignore` / `.gitattributes`） | 总是 |
| `rules/` | `.codebuddy/rules/`（四条，每次会话自动加载） | 总是 |
| `commands/` | `.codebuddy/commands/`（收尾命令 `/wrap-up`） | 总是 |
| `docs/` | `docs/`（地图 + 目录树 + ADR + 需求 + 设计 + 待办 + 会话工作台 + 开发规约） | 总是 |
| `backend/` | `backend/`（Spring Boot 3.5 + MyBatis-Plus + Flyway + JWT） | 总是 |
| `frontend/` | `frontend/`（Vue 3 + Vite + TypeScript + Pinia + Tailwind v4 + shadcn-vue） | 总是 |
| `ci/` | `.github/workflows/` | 总是 |
| `docker/` | 仓库根（`docker-compose.dev.yml`，只起数据库） | 总是 |
| `scripts/` | `scripts/`（四条守卫脚本） | 总是 |
| `testing/` | `docs/testing/` | `--with-testing` |
| `ops/` | `docs/operations/` | `--with-ops` |
| `deploy/` | 仓库根（内含 `.github/`、`scripts/`、`deploy/` 三段） | `--with-deploy` |

生成后恒定存在的目录（空的补 `.gitkeep`）：`docs/adr`、`docs/design`、`docs/development`、
`docs/operations`、`docs/requirements`、`docs/testing`、`docs/todo/archive`、`docs/worklog`。

---

## 四条机械守卫

纪律不靠自觉，靠「不做就过不去」：

```bash
bash scripts/check-doc-links.sh      # 文档链接断了 → 红
bash scripts/check-todo-archive.sh   # 已解决的待办还留在 todo/ → 红
bash scripts/check-module-tests.sh   # 业务模块没有对应测试 → 红
bash scripts/check-version.sh        # 版本字符串与 git tag 不一致 → 红
```

⚠️ 链接守卫只扫**已入库**的文件——`git add` 之前跑等于没验。

---

## 初始化剧本：从「生成完」到「CI 首绿」

生成完不停拍。照 `references/POST-SCAFFOLD.md` 走六阶段：

| # | 阶段 | 步骤 | 过线判据 |
|---|------|------|----------|
| ① | 入库基线 | `git init` → `git add -A` → 跑四条守卫 → 首次提交 | 四条守卫全绿 |
| ② | 依赖就位 | `mvn -B -ntp test`；`npm install && npm run typecheck` | 后端单测通过、前端无类型错误、锁文件入库 |
| ③ | 本地跑通 | 起数据库 → 配本地值 → 起后端 → 起前端 | 后端 200；**首页那行字来自后端** |
| ④ | 门禁复核 | 守卫 + typecheck + `mvn test` 再跑一遍 | 全绿 |
| ⑤ | 入库远程 ⛔ | `gh repo create` → push → 盯 CI | **CI 首绿**（红着不算完） |
| ⑥ | 完成衔接 | 提示手动触发需求打磨 | 提示已给出 |

判据一律「**看产物**」，不看退出码。⑤ 是唯一的硬断点：建远程仓库之前必须停下来问使用者仓库名与公开/私有。

---

## 设计取舍

**只搬通用件。** 判据：这个类换一个业务域名还成不成立？成立 → 搬；只有某个项目的业务决策才需要 → 不搬。

不搬的例子：token 版本号失效机制、账号硬删与清理、头像存储策略、判分工具、Excel 导入导出——
这些都是业务决策，脚手架不该预设。

其他刻意的取舍：

- 依赖版本**钉住**（Spring Boot 3.5.16 / MyBatis-Plus 3.5.17 / jjwt 0.12.7 / springdoc 2.9.1），不写 `<latest>`、不写范围版本；
- 集成测试用 **Testcontainers + 真 MySQL**，不用 H2——迁移脚本是 MySQL 方言，用 H2 等于把「测试环境与真实环境不一致」请回来；
- 前端 Dockerfile **必须 glibc 基础镜像**（`node:22-slim` 非 alpine）——esbuild 没有 x64-musl 官方二进制；
- 模板里**没有任何真实凭据**：密钥、密码、服务器 IP 全是占位符，真实值一律走 GitHub Secrets；
- 色值**不预设**：`tokens.css` 只给中性灰阶 + 一个标 TODO 的主色，产品身份留给新项目自己。

---

## 本仓库结构

```
project-scaffold/
├── SKILL.md                 # Skill 入口：工作流、会话边界、注意事项
├── README.md                # 本文件
├── references/              # 给 AI 看的详细规范
│   ├── POST-SCAFFOLD.md     # ★ 初始化剧本（六阶段 + 断点 + 判据 + 衔接段）
│   ├── VARIABLES.md         # 变量表、占位符语法（只有全大写会被替换）、目录映射
│   ├── DOC-SYSTEM.md        # 文档体系搬了什么、改成什么样
│   ├── TECH-STACK.md        # 后端 / 前端 / Docker / CI 的取舍，以及不搬的业务件
│   ├── FRONTEND-SYSTEM.md   # 前端设计体系三层与色值口径
│   ├── TESTING-SYSTEM.md    # 测试规范；e2e 与探索测试为什么明确不沉淀
│   └── QUALITY-POLICY.md    # 成熟度三档、静态分析与 lint 的取舍
├── scripts/
│   └── scaffold.py          # 生成脚本（仅标准库）
└── templates/               # 模板文件（见上文「生成什么」）
```

---

## 环境要求

生成产物要跑起来，需要：

- **JDK 21+**、**Maven 3.9+**（或用后端 Dockerfile 内的 Maven）
- **Node.js 22+**、**npm**
- **Docker** + Docker Compose（dev 环境只用它起数据库）
- **Python 3.11+**（仅用于跑生成脚本与生成 JWT 随机密钥）

---

## 许可

MIT。见 [LICENSE](./LICENSE)。

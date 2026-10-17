# 设计 skill 清单（外部工具，装在用户级）

**目的**：存档**为什么只用这些、装到哪一步、哪部分被舍弃**——回答「当初为什么这么装」，避免以后重新纠结或误判成遗漏。

**读者**：改前端 UI 的人 / 未来的自己 / AI。

**真相源**：本文件。**用途与禁区**的速查表在项目规则里（每次会话自动加载，那里才是「开工前该看」的）；本文件是**档案**，记录动机与完整性——两处**允许重叠，但速查口径以规则为准**。

> ⚠️ 这些 skill **不是上游的「完全体」**：只装 skill 目录本身，不跑上游的安装器，所以 hooks、CLI 安装器、模板之类的分发层刻意不装。「装到哪一步」以下表为准。

## 一览

<!-- consistency:design-skills:start -->
| # | Skill | 角色 | 安装完整性 | 舍弃了什么 | 舍弃原因 | 什么时候用 |
|---|---|---|---|---|---|---|
| 1 | **impeccable** | 方向 + 确定性门禁（设计总导演） | ⚠️ 部分安装 | `hooks/` **未装** | hooks 每次编辑都自动跑探测，属「守护进程式」介入，把「运行期拉外部二进制」的风险面从「主动调用时」扩到「每次编辑」 | 定方向 / 整体重设计 / 抽设计系统（`init` / `document` / `extract`），及 `critique` / `audit` / `polish` |
| 2 | **make-interfaces-feel-better** | 细节工艺 + 审查格式 | ✅ 整份 | 无 | — | 圆角、阴影 / 描边取舍、悬停 / 按下态、图标描边、动效克制、字体平滑 |
| 3 | **web-design-guidelines** | 无障碍 / 合规审查 | ✅ 整份（单文件） | 无 | — | `review my UI` / `check accessibility` / `audit design`。⚠️ 每次联网拉最新规则 |
| 4 | **shadcn-vue** | 组件用法（官方） | ✅ 整份 | 无 | — | 用 shadcn-vue 组件：`add` / `search` / `docs` / preset / 调试。⚠️ `user-invocable: false`，**只能 AI 自己用，@ 不到** |
| 5 | **ui-ux-pro-max** | 检索型资料库（查询台） | ⚠️ 部分安装：只装运行时核心 | ① `cli/` 安装器；② `templates/`；③ `gallery/` 展示；④ **`--persist` 写盘行为** | ①④ 与「单一信息源」冲突（`MASTER.md` 自称 Source of Truth，会和 `tokens.css` / `DESIGN.md` 打架）；②③ 属分发与展示层，与「只做检索」的定位无关 | **只当查询台**：查色板 / 字体搭配 / 风格 / UX 规则 / 图标 / 图表。⚠️ **只查不写 —— 禁用 `--persist` / `--force`** |
<!-- consistency:design-skills:end -->

**本机没装某个 skill 就跳过它**，并在这里补一行说明（避免下次误判成「漏了」）。

## 共同约定（适用的都写在这里，不逐行重复）

- **都不设 `alwaysApply`**：不常驻注入上下文。
- **都装在用户级目录、不在仓库里**：换机器不跟着走；**按描述命中、非自动加载**，开工时**点名（或 @ 提及）最稳**。

## 逐项细节

### 1. impeccable

| 组件 | 状态 | 说明 |
|---|---|---|
| `SKILL.md` | ✅ | |
| `reference/*.md` | ✅ | |
| `scripts/` | ✅ | 提供确定性的上下文扫描 |
| 引擎二进制 | ⚠️ **运行期拉取** | 首次调用从远端按版本锁拉取并执行；**本项目唯一一处「运行期拉并执行外部二进制」** |
| `hooks/` | ❌ **未装** | 探测器只在被主动调用时跑 |

⚠️ **别用 `npx impeccable install` 装它**：该安装器默认给项目装 hooks，与上表「未装」冲突。

**回退方式**：删掉 skill 下的 `scripts/` 与引擎缓存目录，即回到「只用 guidance」。

### 5. ui-ux-pro-max

**装了（运行时核心）**：`SKILL.md`、`scripts/`、`references/`、`data/`。

**未装（上游顶层，属分发层）**：`cli/` 安装器、`templates/`、`gallery/` 等。

**⚠️ 唯一硬约束**：`--persist` 会往**仓库根**写 `design-system/<slug>/MASTER.md`（自称 "Global Source of Truth"）→ 与本项目「设计真相源 = `frontend/src/styles/tokens.css`」冲突。**禁用 `--persist` / `--force`**；`.gitignore` 已加 `design-system/` 兜底。注意：**不带 `--persist` 的 `--design-system` 只打印、可用**，被砍的只是「写盘副作用」。上游自己的 SKILL.md 仍把 `--persist` 写成推荐用法，**以本项目规则为准**。

**环境前提**：搜索脚本需 **Python 3.x**（`python` / `python3` / `py -3` 任一）。

## 本项目的调整记录

<!-- 增删 skill、改安装范围时在这里追加一行：改动 + 理由。别改上面的历史条目。 -->

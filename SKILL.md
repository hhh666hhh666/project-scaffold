---
name: project-scaffold
description: 按一套「有纪律、能跑、能测」的骨架生成新项目——文档体系（文档地图 / 目录树 / ADR / TODO / 会话工作台 / 收尾命令）+ Spring Boot 后端 + Vue3 前端 + Docker + CI，并带一份初始化剧本。当用户说「我要做一个 xx 系统 / 软件」「搭个新项目」「生成项目骨架」「脚手架」「项目模板」「scaffold」，或要从一个空目录开始一个正经项目时用。
---

# project-scaffold

一句话：**把一个空目录变成一个「有纪律、能跑、能测」的项目**，并把它一路带到 CI 首绿。

它不只是一堆模板文件——文档体系里的每一条纪律都对应一次真实的翻车，
四条机械守卫让「不做就过不去」，初始化剧本负责把新项目从「生成完」带到「CI 首绿」。

---

## 工作流

### 0. 捕获意图句

调用时常伴随一句「**我要做一个 xx 系统 / 软件**」。它有三个用途：

1. **建议项目名 / 包名**（预填生成问答的默认值）；
2. **留作需求打磨的开场背景**（grill 会用）；
3. **不单独落文件**——正式落点是 `docs/requirements/scope.md`，由需求打磨产出。

⚠️ 调用时**没有**这句 → 先问一句「做什么」再开工。别凭空猜一个名字。

### 1. 问变量 → 跑脚本

```bash
python <skill>/scripts/scaffold.py                       # 无参数 → 交互问答
python <skill>/scripts/scaffold.py --name my-app \
    --package com.example.myapp --out E:/code/my-app     # 参数模式
```

脚本只用 Python 标准库，Python 3.11+ 即可（无第三方依赖）。Windows 上若用受管 Python，
路径形如 `~/.workbuddy/binaries/python/versions/3.13.12/python.exe`；Linux / macOS 直接 `python3`。

三个**互相独立**的开关，默认都不开：

| 开关 | 生成什么 | 什么时候开 |
|---|---|---|
| `--with-deploy` | `release.yml`、`docker-compose.prod.yml`、`scripts/server-*.sh`、`deploy/` 模板 | 确定要上线到服务器时 |
| `--with-ops` | `docs/operations/内存策略.md`（预设 2C2G 的算法 + 示例） | 跑在小机器上、或要共用服务器时 |
| `--with-testing` | `docs/testing/README.md` + `系统说明.md`（分层规范与同步纪律） | 准备认真写测试时 |

常用辅助参数：`--dry-run`（只打印清单）、`--force`（覆盖模板产物，不删其他文件）、
`--modules order,product`（额外建空包骨架）。变量表见 `references/VARIABLES.md`。

⚠️ **产物只落在 `--out` 指定的目录**，绝不在当前仓库根生成。

### 2. 生成完不停拍，直接进入初始化

照 `references/POST-SCAFFOLD.md` 的六阶段把新项目从「入库基线」带到「CI 首绿」：

① 入库基线 → ② 依赖就位 → ③ 本地跑通 → ④ 门禁复核 → ⑤ **入库远程（唯一硬断点）** → ⑥ 完成衔接。

判据一律「**看产物**」（端点 200、页面那行字来自后端、守卫打印通过、CI 绿），不看退出码。

### 3. 衔接一：提示式触发需求打磨

初始化完成后打总结并给出可直接复制的触发串，**等用户手动发 `@skill:grill-with-docs`**。
不自动调、不催促；推迟/跳过都允许。⚠️ **不要改 grill-with-docs 的任何文件**。

### 4. 衔接二：提示式触发产品与设计

需求打磨完成后同款提示 `@skill:impeccable`。范围：**当场只做 `init`**（写实 `PRODUCT.md`）；
`document`（派生 `DESIGN.md`）**后置到第一个界面成型后**。

### 5. 收尾：开工提示

给「下一步」建议：按 `docs/requirements/scope.md` 挑**最小的一个功能**，
走一遍完整链路（需求 → ADR → 实现 → 测试 → 提交）。

---

## 会话边界

默认**一气呵成**；允许在大阶段之间断开（生成 / 初始化 / 需求打磨 / 产品与设计）。
续跑靠剧本 + 项目现场自检（`git log` / `docker ps` / 四条守卫 / 已有文档），**不建跨会话状态文件**。

---

## 注意事项（容易做错的地方）

- **不自动调用 grill 或 impeccable**——两处衔接都是「提示 + 用户手动触发」。
- **`PRODUCT.md` 与 `DESIGN.md` 只建空文件**，内容是 impeccable 的产物；别替它写骨架。
- **不要在别的仓库里生成产物**；`--out` 必须显式给或交互确认。
- **模板里没有也不该有真实凭据**（密钥、密码、服务器 IP 全是占位符）。
- **色值不预设**：`tokens.css` 给的是中性灰阶 + 一个标 TODO 的主色，那是新项目自己的产品身份。
- 生成后建议立刻自检一次：`grep -rnE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' <out>/`（除占位模板的示例日期外不该有别的）。

---

## references

| 文件 | 看什么 |
|---|---|
| `references/POST-SCAFFOLD.md` | ★ 初始化剧本（六阶段 + 断点 + 判据 + 本机坑 + 衔接段） |
| `references/VARIABLES.md` | 变量表、占位符语法（只有全大写会被替换）、目录映射 |
| `references/DOC-SYSTEM.md` | 文档体系搬了什么、改成什么样、地图与树为什么成对 |
| `references/TECH-STACK.md` | 后端 / 前端 / Docker / CI 的取舍，以及**不搬**的业务件 |
| `references/FRONTEND-SYSTEM.md` | 前端设计体系三层（规则 / 档案 / 真相源）与色值口径 |
| `references/TESTING-SYSTEM.md` | 测试规范搬了什么；e2e 与探索测试为什么**明确不沉淀** |
| `references/QUALITY-POLICY.md` | 成熟度三档、静态分析与 lint 的取舍、要上的最小代价路径 |

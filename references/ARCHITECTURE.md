# 流程架构：能力怎么分层

![project-scaffold 架构](./architecture.svg)

源文件是 [`architecture.dot`](./architecture.dot)，SVG 由 Graphviz 生成；改了脚本职责或模板目录后，
图与代码一起更新。本文件讲**流程与能力分层**；运行时、测试、CI 与发布等技术栈见
[`TECH-ARCHITECTURE.md`](./TECH-ARCHITECTURE.md)。

## 四层怎么读

### ① 使用入口

- **主人**提出「我要做一个 xx 系统」。
- **AI 编码助手**触发 `SKILL.md`。
- `SKILL.md` 是唯一编排入口：负责对话收集变量、要求 dry-run 预览、等待确认，
  再决定是进入生成、初始化，还是补装配套 skill。

### ② 仓库的四类能力

| 能力 | 组件 | 输入 | 输出 |
|---|---|---|---|
| 生成 | `scripts/scaffold.py` + `templates/` | 已确认的参数、模板、可选开关 | 新项目文件；最后原子发布 `.scaffold.json` |
| 初始化 | `references/POST-SCAFFOLD.md` | 刚生成的项目、所选数据库路径 | 六阶段推进到 CI 首绿 |
| skill 安装 | `scripts/fetch_skills.py` + `references/SKILL-SOURCES.json` | 锁定提交、用户级 skill 目录 | 缺失的 skill；每个带 `.fetched.json` |
| 维护门禁 | `tests/` + `scripts/check_consistency.py` + `.github/workflows/selftest.yml` | 模板、版本表、skill 清单、生成物 | 离线回归、一致性结果、冒烟结论 |

四类能力互不替代：

- 生成器不负责数据库联通和 CI；
- 初始化剧本不修改模板；
- 安装器不执行上游内容；
- 维护门禁不联网、不启动 Docker / Maven / npm。

### ③ 产出

- **新项目骨架**：`backend/`、`frontend/`、`docs/`、`scripts/`（四条守卫）、`.github/`（CI 与 Dependabot）
  以及根目录的 `.scaffold.json`。
- **用户级 skill 目录**：只装 skill 目录本身，不装 hooks、安装器、模板；已有 skill 不覆盖。

`.scaffold.json` 与 `.fetched.json` 都是**来源记录**，不是会话进度，也不是当前配置的真相源。

### ④ 外部系统

- **生成项目的 GitHub 远程**：初始化阶段建仓并 push，CI 首绿后才算完成；Dependabot 只提升级 PR。
- **GitHub 官方 skill 仓库**：安装器按锁定完整提交获取，不追分支头；`--outdated` 只报告差异。

## 关键边界

1. **产物只落在 `--out` 指定的目录**，绝不在当前仓库根生成。
2. **dry-run 无副作用**：不创建目录、不写记录；文本与 JSON 使用同一份文件清单。
3. **`.scaffold.json` 最后写**：模板中途失败不会发布新记录，也不宣称整个目录事务成功。
4. **模板里没有真实凭据**：密钥、密码、服务器地址都是占位符。
5. **外部 skill 不随仓库分发**：本地缺失才安装，先预览再确认，绝不覆盖已有目录。
6. **仓库级 CI 分两层**：每次 push 的 `selftest.yml` 离线跑 Python 回归、一致性检查和生成物冒烟；
   定时的 `full-build.yml` 才联网做真实 Maven / npm 构建。两者都不覆盖真实数据库、浏览器或上游拉取。

## 重新生成 SVG

```bash
dot -Tsvg references/architecture.dot -o references/architecture.svg
```

需要 [Graphviz](https://graphviz.org/)。图内字体使用 `Microsoft YaHei`，在缺少该字体的系统上会由渲染器替换，
不影响布局。只改文案时直接改 `.dot` 再重新生成，不手工编辑 SVG。

改完跑一次图漂移检查，确认 `.dot`、`.svg` 与文档引用一致：

```bash
python scripts/check_consistency.py --only diagrams
```

它只比对结构、文字与登记过的事实，不检查颜色、布局和文字重叠；这些仍需人眼看图。

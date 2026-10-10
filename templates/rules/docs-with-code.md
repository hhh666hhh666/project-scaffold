---
description: 改代码 = 改文档——单一信息源（能从代码查到的事实文档只写「去哪看」），移动/删除文件要全仓搜旧名。
alwaysApply: true
---

# 改代码 = 改文档

## 单一信息源（硬纪律）

**判据**：一条事实的真相源若是**某个随时会变的东西**——代码、脚本、`.env.example`、迁移脚本、接口文档、git 状态、控制台——文档只写**去哪看**，不复制内容。
**文档与代码冲突时以代码为准，并顺手把文档改对。**

抄进文档的派生事实必然会漂：版本号、依赖版本、文件清单、命令输出全文、配置默认值，都属于这一类。

## 改动 → 该去哪儿改

不确定就先读 `docs/README.md` 的文档地图表，别猜。

| 改了 | 去检查 |
|------|--------|
| 后端接口 / DTO / VO | `docs/design/API.md`（细节以接口文档运行时为准） |
| 表结构 / 实体 / 迁移脚本 | `docs/design/数据模型.md` |
| 核心业务规则与状态流转 | `docs/design/` 下对应主题 |
| 导入导出格式 | `docs/design/` 下对应主题 |
| 前端结构 / 路由 / 状态 | `docs/design/前端.md` |
| 部署、compose、`scripts/` | `docs/operations/` |
| 配置、密钥、`.env` | `docs/operations/configuration.md` |
| 测试策略 | `docs/testing/` |
| CI / 镜像构建 | `.github/workflows/` |
| 领域词汇 | 根 `CONTEXT.md` |
| ADR（新卡 / 改结论 / 推翻与收窄） | `docs/requirements/scope.md`——核对**「已定范围与约束」表与「明确不做」清单**要不要跟着改：scope 是范围的真相源、ADR 是「为什么」，约束表里的 ADR 链接必须指向**当前**结论，漏改 = 索引指旧话 |
| 受众 / 语气 / 定位（产品真相） | 根 `PRODUCT.md` |
| 本次迭代交付项 | `CHANGELOG.md` |

## 移动 / 删除 / 重命名文件（最容易漏，必须做）

1. 用 `git mv`，别手动重开文件。
2. 全仓搜旧名，**包括非 Markdown 文本**（注释、脚本 `echo`、Dockerfile、YAML、`.env.example`）：

   ```bash
   git grep -n '<旧名或旧路径>'
   ```

3. 改完跑一次链接自检脚本。它查两类：md 相对链接、以及脚本/注释里提到的 `docs/ scripts/ .github/` 路径。**新增的文件要先 `git add`**——它只扫已跟踪文件，没 add 就等于没验。CI 上有同名 job 会再验一遍。
4. md 里写**示例或虚构路径用行内代码** `` `foo/bar.md` ``，别写成 `[](foo/bar.md)`——脚本只查链接，不查行内代码。

## 收尾

- 结构性决策：结论进 `docs/adr/00NN-*.md`，**被否的选项写进同一张卡的 Considered Options**。不另设「决策过程」文档类别；没结论的过程记录留在 `docs/worklog/`。
- **改完 ADR 必须同步 `docs/requirements/scope.md`**：新结论属范围口径 → 进「已定范围与约束」表；被推翻 / 收窄 → 对应行与「明确不做」条目一起改掉。与范围无关的纯内部决策可不入表，但**核对本身不可跳**。
- 新的未决事项**不许**写在任何文档正文里 → `docs/todo/`。
- 提交前跑一次链接自检脚本，全绿再 commit。

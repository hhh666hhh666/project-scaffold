# 文档索引

这份索引只回答一个问题：**东西在哪**。内容本身一律留在各自的文件里，这里不复述。
想一眼看清「文档散在哪、长什么样」 → [`目录结构.md`](./目录结构.md)（那两棵带注释的目录树）。
**两处是同一批文件的两个视角，改一处要同步另一处。**

## 文档地图

「真相源」一列是这份文档的**事实凭据在哪**——冲突时以真相源为准，并顺手修文档。
写「本文件」表示这份文档自己就是源头，没有别处可查。

| 路径 | 用途 | 读者 | 真相源 |
|------|------|------|--------|
| [../README.md](../README.md) | 上手：定位、功能、跑起来、配置要点、CI 与部署 | 所有人 | 代码与脚本 |
| [../GLOSSARY.md](../GLOSSARY.md) | 领域术语表（只收本项目独有的词，不含实现） | 读代码的人 | 本文件 |
| [../PRODUCT.md](../PRODUCT.md) | 产品真相：受众 / 用途 / 定位 / 语气 / 约束 | 判断「某个设计对不对」的人 | 本文件（由 impeccable 生成） |
| [../DESIGN.md](../DESIGN.md) | 视觉系统的**可读快照**（色板 / 排版 / 材质口径） | 改前端视觉的人 | **从 `frontend/src/styles/tokens.css` 派生**；过时了重新生成 |
| [../CHANGELOG.md](../CHANGELOG.md) | 版本变更记录 | 所有人 | `git tag` |
| [../AGENTS.md](../AGENTS.md) | **给 AI 的规矩**（跨工具摘要，只做路由） | AI / 未来的自己 | `.codebuddy/rules/` |
| [../CLAUDE.md](../CLAUDE.md) | Claude Code 的入口：只导入 `AGENTS.md` 与四条规则，不写内容 | Claude Code | `AGENTS.md` + `.codebuddy/rules/` |
| [../.codebuddy/commands/wrap-up.md](../.codebuddy/commands/wrap-up.md) | 收尾自检：把未决事项落 `docs/todo/`、补文档与引用、跑守卫脚本 | AI / 收尾时 | 本文件 |
| [../scripts/${LINK_CHECK_SCRIPT}](../scripts/${LINK_CHECK_SCRIPT}) | md 相对链接与路径引用自检，提交前跑 | 提交代码的人 | 文件系统 |
| [../scripts/${TODO_ARCHIVE_SCRIPT}](../scripts/${TODO_ARCHIVE_SCRIPT}) | 断言已结案的待办都已移入 `docs/todo/archive/` | 结案待办的人 / CI | 文件系统 |
| [../scripts/${MODULE_TEST_SCRIPT}](../scripts/${MODULE_TEST_SCRIPT}) | 断言每个带 Controller 的模块都配了测试类 | 加新模块的人 / CI | 文件系统 |
| [../scripts/${VERSION_SCRIPT}](../scripts/${VERSION_SCRIPT}) | 版本号与 `git tag` 对齐自检；非 tag 提交上自动跳过 | 要打 tag 的人 / CI | `git tag` |
| [requirements/scope.md](./requirements/scope.md) | 定位、范围、**明确不做**、已定约束 | 判断某个改动越没越界的人 | 本文件 + 各条 ADR |
| [design/API.md](./design/API.md) | 怎么看真实接口、通用响应与错误约定 | 对接接口或改 Controller 的人 | 接口文档与各 Controller |
| [design/数据模型.md](./design/数据模型.md) | 实体关系、生命周期、历史一致性 | 改数据结构或写查询的人 | 迁移脚本 |
| [design/前端.md](./design/前端.md) | 前端页面流、路由、状态与 API 边界 | 改前端的人 | `frontend/src/` |
| [design/设计skill清单.md](./design/设计skill清单.md) | 外部设计 skill 的角色与禁区（档案；速查见 `.codebuddy/rules/design-skills.md`） | 改前端 UI 的人 / AI | 本文件 |
| [adr/](./adr/) | **决策结论**卡片（Status / Considered Options / Consequences） | 查「为什么这么定」的人 | ADR 自身 |
| [development/contributing.md](./development/contributing.md) | 分支 / 提交 / PR 约定与文档纪律 | 要提交代码的人 | `git log` |
| [todo/](./todo/) | **未决事项唯一入口** | 想知道「还有什么没定」的人 | 各待办文件 |
| [worklog/](./worklog/) | AI **会话**的实时进度（正在做什么 / 接下来 / 已做完） | 只对创建它的那次会话有意义，**其他会话不必读** | 各文件自身 |
| [目录结构.md](./目录结构.md) | **两棵带注释目录树**：① 仓库根的文档散在哪 ② `docs/` 体系内部 | 新人 / 冷启动的 AI | 文件系统 |

**可选章节**（开关式生成，没生成就没有这几个文件）：`docs/testing/README.md` 与 `docs/testing/系统说明.md`（测试体系规范）、`docs/operations/内存策略.md`（内存策略）、`deploy/` 与 `.github/workflows/release.yml`（部署）。

## 决策只有 adr 记

- **`adr/`** 是**结论**。一条决策一张卡，写完不再改；要推翻就新增一条并标注取代了谁。
  查「**为什么**这么定」看这里。
- **被否的选项写在同一张卡的 Considered Options 里**——所以查「当时**有没有考虑过**某个方案」，也是看这里。
- **哪条决策够格写成 ADR**、格式与编号规则，见 [adr/README.md](./adr/README.md)。
- **`worklog/`** 是**过程**（一次会话一份），但它只对创建它的那次会话有意义，**不是事实源**。

## 未决事项只有一个入口：`docs/todo/`

规则：**任何「未定 / 待定 / 以后再说」只能存在于 `docs/todo/`**，docs 里一律链接过去，不许在文档中间开第二份待办清单。

命名与索引规则见 [todo/README.md](./todo/README.md)。那个文件里还有一张「已定，不用再想」的表——那些已经拍板并写进 ADR，列出来是为了防止以后重新纠结一遍。

这条纪律对 AI 同样生效：项目规则里有**总是加载**的一条专门管它（见 `.codebuddy/rules/`），收尾时可以用 `/wrap-up` 自检。

## 单一信息源纪律

**判据**：能从代码、脚本、`.env.example`、迁移脚本或接口文档运行时得到的事实，文档只写「去哪看」，不复制一份。
典型反例：把 `.env.example` 的变量表抄进文档、把部署脚本的步骤抄进文档。

**文档与代码冲突时以代码为准**，并且顺手把文档改对——不是等下次。抄进文档的派生事实必然会漂。

## 常见入口

| 你想做的事 | 从哪开始 |
|------------|----------|
| 在一台新机器上跑起来 | [../README.md](../README.md) |
| 知道某个词在代码里指什么 | [../GLOSSARY.md](../GLOSSARY.md) |
| 判断某个改动超不超当前范围 | [requirements/scope.md](./requirements/scope.md) |
| 改代码前摸清设计与规则 | [design/](./design/) 下对应主题 + 对应 ADR |
| 想知道还有什么没定 | [todo/](./todo/) |
| 想一眼看清文档都在哪 | [目录结构.md](./目录结构.md) |

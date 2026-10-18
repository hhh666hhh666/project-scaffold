# 初始化剧本（生成之后怎么走）

**适用**：骨架刚生成完，工作目录 = 新项目根。
**前置**：进入本剧本前，已经用最终参数完成 `--dry-run`，向使用者展示参数、目标目录状态、开关和文件计划，并在确认后正式生成。
这个生成确认只覆盖「写入骨架文件」；后面的 commit、push、建远程仓库、拉取配套 skill 仍按本剧本的确认点执行。
**节奏**：默认**一气呵成**；允许在**大阶段之间**断开（生成 / 初始化 / 需求打磨 / 产品与设计），
断开后靠本剧本 + 项目现场自检续跑，**不建跨会话状态文件**。

**权限口径**：三类动作做之前必须先问使用者，拿到确认再动手：

1. **每次 `git commit` 与 `git push`**——先列出要提交的文件与提交信息；同一阶段的多笔可以一次确认；
2. **建远程仓库**——要问仓库名与公开/私有（第 ⑤ 阶段）；
3. **拉取本地没有的配套 skill**——要写进使用者的 skill 目录、并从网上拉代码（第 ⑥ 阶段）。

其余（跑命令、改项目里的文件、起服务）照常推进。两处衔接是「提示式触发」（见衔接段），由使用者手动发话接上。

---

## 六阶段表

| # | 阶段 | 谁做 | 步骤 | 过线判据 | 停下点 |
|---|------|------|------|----------|--------|
| ① | **入库基线** | AI | `git init` → 全量 `git add` → 跑四条守卫 → 首次提交 | 四条守卫**全绿**；`git log` 有一条提交 | 提交前确认 |
| ② | **依赖就位** | AI | 后端 `mvn -B -ntp test`；前端 `npm install`（生成锁文件）后 `npm run typecheck` | 后端 3 个测试通过；前端 typecheck 无错；`package-lock.json` 已入库 | 提交前确认 |
| ③ | **本地跑通** | AI + 用户 | 选择 Docker MySQL 或专用外部 MySQL → 配本地值（随机 JWT 密钥、端口核对）→ 起后端 → 起前端 | 有可用 MySQL 时：后端健康端点 200；**前端页面能开且那行字来自后端**；没有数据库时：只记录基础门禁完成，联通项明确为受阻 | — |
| ④ | **门禁复核** | AI | 四条守卫 + typecheck + `mvn test` 再跑一遍 | 全绿 | — |
| ⑤ | **入库远程** | **用户拍板** | 问仓库名与公开/私有 → `gh repo create` → push → 盯 CI | **CI 首绿**（红不算完） | ⛔ 建仓与推送前确认 |
| ⑥ | **完成衔接** | AI 提示 | 检查配套 skill → 缺了先问再拉 → 打总结 + 提示用户手动触发需求打磨 | 提示已给出；worklog 记下「等待触发」 | 拉取前确认；自然断点 |

### ① 入库基线

```bash
cd <项目根目录>
git init -b master
cp .env.example .env                     # 填真值（至少把 JWT 密钥换成随机值）
git add -A
bash scripts/check-doc-links.sh
bash scripts/check-todo-archive.sh
bash scripts/check-module-tests.sh
bash scripts/check-version.sh            # 没 tag 会跳过，正常
git commit -m "chore: 初始化项目骨架"      # ⚠️ 先给使用者看文件清单与提交信息，确认后再提交
```

⚠️ **顺序不能反**：链接守卫只扫**已入库**的文件，`git add` 之前跑等于没验。
判据是「看产物」——四条都打印「通过/没有发现断链」。

`.scaffold.json` 会随 `git add -A` 一起入库。它记录生成来源与参数，**不证明初始化完成**，
也不能替代四条守卫、后端单测或数据库联通验收。

### ② 依赖就位

```bash
cd backend && mvn -B -ntp test
cd frontend && npm install && npm run typecheck
```

⚠️ `npm install` 之后要把生成的 `package-lock.json` **提交进库**（`npm ci` 依赖它，
CI 上用它做缓存 key，版本守卫也比它）。

✅ 锁文件入库、仓库推到 GitHub 之后，`.github/dependabot.yml` 才会开始工作：每周给 Maven / npm /
GitHub Actions 各提一次升级 PR。它只提案，不自动合并、不触发部署，升级 PR 走的是普通 CI；
补丁 / 小版本按组件家族分组，大版本单独提，合并与否由使用者判断。基础镜像与 MySQL 镜像**不在覆盖范围**。

### ③ 本地跑通

先选一条数据库路径，不把 Docker 当成唯一前置：

**路径 A：Docker 启动本机 MySQL（推荐）**

```bash
docker compose -f docker-compose.dev.yml up -d          # 只起数据库
python -c "import secrets;print(secrets.token_hex(32))" # 生成 JWT 密钥，写进 .env（给 compose 用）
cd backend && mvn -B -ntp spring-boot:run               # 起后端
```

**路径 B：使用专用本机或远程 MySQL**

没有 Docker 但有可用 MySQL 时，先为本项目准备专用数据库和账号，再在启动后端的 shell 中显式覆盖连接配置：

```bash
export SPRING_DATASOURCE_URL='jdbc:mysql://127.0.0.1:3306/<数据库名>?useUnicode=true&characterEncoding=utf8&useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai'
export SPRING_DATASOURCE_USERNAME='<开发账号>'
export SPRING_DATASOURCE_PASSWORD='<开发密码>'
export <前缀>_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')"
cd backend && mvn -B -ntp spring-boot:run
```

Flyway 会对这个目标库执行迁移；不要把生产库当作本地开发库。`docker-compose.dev.yml` 的 `MYSQL_PORT`
只改变容器端口映射，不会自动改变宿主机 Maven 使用的 JDBC URL。

**路径 C：暂时没有任何 MySQL**

仍可完成生成、四条守卫、后端纯单测和前端 `typecheck` / `build`，但必须把以下事项记为“未验证 / 受阻”：
数据库迁移、后端启动、接口健康端点、前后端页面联通。不能用 H2、关闭 Flyway 或假造接口返回来把这段标成“本地跑通”。
后续获得 Docker 或专用 MySQL 后，从路径 A/B 继续，并补做下面的真实联通判据。

**有 MySQL 时的联通判据**

```bash
# 路径 A 已由 compose 提供数据库；路径 B 使用上面三个 SPRING_DATASOURCE_* 变量
curl --noproxy '*' -fsS http://127.0.0.1:8080/actuator/health >/dev/null && echo "后端 200 ✓"
cd frontend && npm run dev
```

浏览器打开 `http://127.0.0.1:5173/`，**首页那行「后端返回：hello, world」是后端给的**——
这一条同时证明代理、鉴权白名单、响应解包都通了。


### ④ 门禁复核

把 ① 的四条守卫 + ② 的两条命令再跑一遍。这次是在「装了依赖、起了服务」之后，
能发现骨架阶段发现不了的问题（比如格式化后产生的文件被误提交）。

### ⑤ 入库远程（⛔ 硬断点）

**在这里停下问用户**：仓库名、公开还是私有，以及确认可以推送。拿到答案再继续：

```bash
gh repo create <仓库名> --public/--private --source=. --push
gh run watch --exit-status          # 盯到 CI 首绿；红了就修，别带着红的 CI 收工
```

⚠️ **CI 首绿才算这一步完成**。红着不算，也不要「先合了下次修」。
修 CI 产生的每一笔提交与推送，同样先确认再做。

### ⑥ 完成衔接

见下文「衔接段」：先检查配套 skill，再给触发提示。

---

## 首日纪律

- **初始化本身就是这个项目的第一份 worklog**：`docs/worklog/YYYY-MM-DD-HHmm-<6位hex>.md`，
  收尾把「本轮状态」改成 `本轮完成`。
- 全程走**项目自己的规矩**：要动文件就先建工作台；有未决的落 `docs/todo/`（并回索引表补行）；
  有拍板的写 ADR。这是「即测即用」——规矩第一次被执行的场景就是它自己。
- 提交用 Conventional Commits（`chore:` / `docs:` / `feat:` …），一次改动一个主题。

---

## 常见坑（多见于 Windows + Git Bash）

| 症状 | 处理 |
|---|---|
| Docker 起不来 / `docker ps` 连不上守护进程 | 有 Docker 时手动点开 Docker Desktop；没有 Docker 但有专用 MySQL 时走路径 B；两者都没有则完成基础门禁并把数据库联通记为受阻，不能用旧容器存活端口冒充本次验证 |
| 后端明明配了 8080，却报别的端口被占用 | 环境里注入了 `SERVER_PORT`（或 `SERVER__PORT`）之类的变量，顶掉了配置。起服务前 `unset SERVER__PORT SERVER_PORT` |
| `*.sh` 报 `bad interpreter` | 文件成了 CRLF。`.gitattributes` 已强制 LF，编辑器可能改回去，提交前看 `git diff` 有没有整文件变动 |
| npm 装不上 / 锁文件跨平台出问题 | 删掉 `package-lock.json` 在**目标平台**上重新 `npm install`，别手改锁文件 |
| 探本地端口时通时不通 | `curl` 走了系统代理。探本地服务一律加 `--noproxy '*'` |
| 命令里 `node` / `python` 不是想要的那个版本 | 机器上装了多个版本。先 `which node` / `which python` 看实际命中哪个，必要时用全路径 |
| 推 git / 拉依赖时某些外网域名连不上 | 网络需要代理时，给 git / npm / Maven 分别配上代理再试 |

---

## 可续机制（断开之后怎么接上）

**不建跨会话状态文件**，靠现场自检定位断点：

```bash
git log --oneline -5                 # 已提交到哪一步
git status --porcelain               # 有没有未提交的改动
docker ps --format '{{.Names}}'      # 若选 Docker 路径，数据库在不在跑
# 若选外部 MySQL，改用 mysqladmin ping 或实际连接检查；没有数据库则保留受阻项
bash scripts/check-doc-links.sh      # 文档守卫绿不绿
ls docs/worklog/                     # 上一份工作台写到哪了
```

对照六阶段表就能判断「上次停在哪」。

---

## 衔接段：两处「提示式触发」

**统一为一种仪式**：AI 打总结 + 给可直接复制的触发串，**等用户手动触发**；AI 不自动调、不催促。
推迟或跳过都允许（跳过只在总结里记一笔，不纠缠）。停在这里算自然断点，把「等待触发」写进 worklog。

### 先检查配套 skill 在不在

用到的 skill 都来自官方仓库，**不随本 skill 分发**，分两组：

<!-- consistency:source-skills:start -->
| 组 | skill | 官方仓库 | 许可 |
|---|---|---|---|
| 衔接用 | `grill-with-docs`（转调 `grilling` + `domain-modeling`） | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| 衔接用 | `impeccable`（同时也是设计组的一员） | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 |
| 设计组 | `make-interfaces-feel-better` | [jakubkrehel/make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better) | MIT |
| 设计组 | `web-design-guidelines` | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 仓库未声明许可（只拉到本机，不再分发） |
| 设计组 | `shadcn-vue` | [unovue/shadcn-vue](https://github.com/unovue/shadcn-vue)（默认分支 `dev`） | MIT |
| 设计组 | `ui-ux-pro-max` | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT |
<!-- consistency:source-skills:end -->

脚本里 `design` 是设计组 5 个的别名（含 `impeccable`）。

**拉到的不是上游「完全体」**：只复制 skill 目录、不跑上游的安装器，所以 hooks、CLI 安装器、模板、展示页都不装。
具体差在哪，`--check` 会在每个缺失项下面用缩进的 `-` 标出来，生成项目的 `docs/design/设计skill清单.md` 里也有档案。

1. **当前会话的可用 skill 列表里已经有** → 那几个不用碰脚本；全都有就直接进下面的衔接。
2. **有缺的** → 先只查不拉，看缺哪些、从哪个仓库的哪个固定提交拉、各自装到哪一步：
   ```bash
   python <skill>/scripts/fetch_skills.py --dest <skill 目录> --check grill-with-docs design
   ```
   `<skill 目录>` 是当前 AI 工具的用户级 skill 目录：WorkBuddy 为 `~/.workbuddy/skills`，
   Claude Code 为 `~/.claude/skills`；其他工具查它自己的文档。锁定提交在
   `references/SKILL-SOURCES.json`，`--check` 不联网、不写盘。
3. **把这份清单给使用者看，确认后**去掉 `--check` 再跑一次。脚本只补缺的、不覆盖已有的；
   安装严格使用锁定提交，目标目录没有 `SKILL.md` 或是普通文件时报告冲突、不接管。
   装完打印每个 skill 的来源 commit（缩写；完整值与该目录的原始文件摘要写在它自己的 `.fetched.json`），
   **原样记进 worklog**。**一次确认覆盖整份清单**，别逐个问。
4. 多数工具只在会话开始时扫描 skill 目录：装完当前会话看不到，就提示使用者**开新会话再触发**——
   这正好落在自然断点上。
5. 使用者不同意、或拉取失败 → 在总结里说明这一步本来要做什么、去哪装，并落一条 `docs/todo/`，**不卡住收尾**。
   部分仓库失败时，已完成的安装保留、未完成项列清楚，不用「整个失败」掩盖已经发生的修改。
   设计组缺了不影响收尾：`design-skills.md` 本来就写明「没装就跳过」。
6. 以后想确认是否与上游有差异，可以单独跑只读检查：
   ```bash
   python <skill>/scripts/fetch_skills.py --dest <skill 目录> --outdated grill-with-docs design
   ```
   它分别报告来源记录是否有效、本机文件有没有被改、锁定基线与上游分支头是否不同。
   **提交号不同不等于落后**；这条命令不安装、不升级、不覆盖，升级与否由使用者另行决定。
   此前手工装过、没有 `.fetched.json` 的，只会显示「来源未知」，脚本不会猜一个来源补上。

⚠️ 不要用 `npx impeccable install` 代替脚本：它默认给项目装 hooks，与本项目「impeccable 不装 hooks」的约定冲突。
⚠️ `ui-ux-pro-max` 的上游文档把 `--persist` 当推荐用法，**照抄会违反** `design-skills.md` 里「只查不写」的硬禁区，以后者为准。
已经通过插件装过官方全家桶的，别再用脚本装一份——同名 skill 会出现两次。

触发写法按工具不同：WorkBuddy 是 `@skill:<名字>`，Claude Code 是 `/<名字>`；下文以 WorkBuddy 写法举例。

### 衔接一 · 初始化 → 需求打磨

初始化完成（CI 首绿）后，AI 的总结里要有这段要点：

> ✅ 初始化完成（本地跑通 / 门禁全绿 / 已入库 / CI 首绿）。
> 下一步是**需求打磨**——由 grill-with-docs 做。
> 它是手动触发的：发一句 `@skill:grill-with-docs`（Claude Code 里是 `/grill-with-docs`）接上即可；想先收工就停在这（可续），想跳过说一声。

⚠️ **不要改 `grill-with-docs` 的任何文件**（尤其它的 `disable-model-invocation` 标志）——
「提示 + 手动触发」这个设计正是以那个标志为前提的。

### 衔接二 · 需求打磨 → 产品与设计

grill 完成后同款提示（`@skill:impeccable` / `/impeccable`）。这一步的范围：

- **当场只做 `init`**——把 `PRODUCT.md` 从空占位写实；
- **`document`（`DESIGN.md`，从现有代码派生）后置到「第一个界面成型之后」**再跑。
  剧本里要写明这个后续触发点，别在骨架阶段跑（那时没东西可派生）。

### 收尾 · 开工提示

全部完成后给「下一步」建议：按 `docs/requirements/scope.md` 挑**最小的一个功能**，
走一遍完整链路（需求 → ADR → 实现 → 测试 → 提交），把这套规矩真正跑一遍。

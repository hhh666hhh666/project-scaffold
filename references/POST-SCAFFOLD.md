# 初始化剧本（生成之后怎么走）

**适用**：骨架刚生成完，工作目录 = 新项目根。
**节奏**：默认**一气呵成**；允许在**大阶段之间**断开（生成 / 初始化 / 需求打磨 / 产品与设计），
断开后靠本剧本 + 项目现场自检续跑，**不建跨会话状态文件**。

**权限口径**：本地提交与推送由 AI 自行完成（照现行协作习惯）；
**全程只有一个硬断点：建远程仓库之前**（要问仓库名与公开/私有）。
另外两处是「提示式触发」（见第 6 节），由用户手动发话接上。

---

## 六阶段表

| # | 阶段 | 谁做 | 步骤 | 过线判据 | 停下点 |
|---|------|------|------|----------|--------|
| ① | **入库基线** | AI | `git init` → 全量 `git add` → 跑四条守卫 → 首次提交 | 四条守卫**全绿**；`git log` 有一条提交 | — |
| ② | **依赖就位** | AI | 后端 `mvn -B -ntp test`；前端 `npm install`（生成锁文件）后 `npm run typecheck` | 后端 3 个测试通过；前端 typecheck 无错；`package-lock.json` 已入库 | — |
| ③ | **本地跑通** | AI + 用户 | 起数据库 → 配本地值（随机 JWT 密钥、端口核对）→ 起后端 → 起前端 | 后端健康端点 200；**前端页面能开且那行字来自后端** | — |
| ④ | **门禁复核** | AI | 四条守卫 + typecheck + `mvn test` 再跑一遍 | 全绿 | — |
| ⑤ | **入库远程** | **用户拍板** | 问仓库名与公开/私有 → `gh repo create` → push → 盯 CI | **CI 首绿**（红不算完） | ⛔ **硬断点** |
| ⑥ | **完成衔接** | AI 提示 | 打总结 + 提示用户手动触发需求打磨 | 提示已给出；worklog 记下「等待触发」 | 自然断点 |

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
git commit -m "chore: 初始化项目骨架"
```

⚠️ **顺序不能反**：链接守卫只扫**已入库**的文件，`git add` 之前跑等于没验。
判据是「看产物」——四条都打印「通过/没有发现断链」。

### ② 依赖就位

```bash
cd backend && mvn -B -ntp test
cd frontend && npm install && npm run typecheck
```

⚠️ `npm install` 之后要把生成的 `package-lock.json` **提交进库**（`npm ci` 依赖它，
CI 上用它做缓存 key，版本守卫也比它）。

### ③ 本地跑通

```bash
docker compose -f docker-compose.dev.yml up -d          # 只起数据库
python -c "import secrets;print(secrets.token_hex(32))" # 生成 JWT 密钥，写进 .env（给 compose 用）
cd backend && mvn -B -ntp spring-boot:run               # 起后端
curl --noproxy '*' -fsS http://127.0.0.1:8080/v3/api-docs >/dev/null && echo "后端 200 ✓"
cd frontend && npm run dev
```

⚠️ `mvn spring-boot:run` **不读 `.env`**。宿主机直跑时没设 `<前缀>_JWT_SECRET` 是正常的：
后端会打一条「正在使用 JWT 默认密钥」的警告并改用随机密钥（重启需重新登录），不影响跑通。
想要固定密钥就在起后端的那个 shell 里 `export <前缀>_JWT_SECRET=...`。

判据两条，都要真的看到：
- 后端 `/v3/api-docs` 返回 200；
- 浏览器打开 `http://127.0.0.1:5173/`，**首页那行「后端返回：hello, world」是后端给的**——
  这一条同时证明代理、鉴权白名单、响应解包都通了。

### ④ 门禁复核

把 ① 的四条守卫 + ② 的两条命令再跑一遍。这次是在「装了依赖、起了服务」之后，
能发现骨架阶段发现不了的问题（比如格式化后产生的文件被误提交）。

### ⑤ 入库远程（⛔ 硬断点）

**在这里停下问用户**：仓库名、公开还是私有。拿到答案再继续：

```bash
gh repo create <仓库名> --public/--private --source=. --push
gh run watch --exit-status          # 盯到 CI 首绿；红了就修，别带着红的 CI 收工
```

⚠️ **CI 首绿才算这一步完成**。红着不算，也不要「先合了下次修」。

### ⑥ 完成衔接

见下一节。

---

## 首日纪律

- **初始化本身就是这个项目的第一份 worklog**：`docs/worklog/YYYY-MM-DD-HHmm-<6位hex>.md`，
  收尾把「本轮状态」改成 `本轮完成`。
- 全程走**项目自己的规矩**：要动文件就先建工作台；有未决的落 `docs/todo/`（并回索引表补行）；
  有拍板的写 ADR。这是「即测即用」——规矩第一次被执行的场景就是它自己。
- 提交用 Conventional Commits（`chore:` / `docs:` / `feat:` …），一次改动一个主题。

---

## 本机坑清单（⚠️ 本机专属：Windows + Git Bash）

| 症状 | 处理 |
|---|---|
| Docker 起不来 / `docker ps` 连不上守护进程 | Docker Desktop 不会自启，**手动点开**再等约一分钟；它退出后旧容器仍在，别被存活的端口骗了 |
| 后端明明配了 8080 却报 `Port 51293 in use` | 环境注入了 `SERVER__PORT` / `SERVER_PORT`，会顶掉配置。起服务前 `unset SERVER__PORT SERVER_PORT` |
| `*.sh` 报 `bad interpreter` | 文件成了 CRLF。`.gitattributes` 已强制 LF，编辑器可能改回去，提交前看 `git diff` 有没有整文件变动 |
| npm 装不上 / 锁文件跨平台出问题 | 删掉 `package-lock.json` 在**目标平台**上重新 `npm install`，别手改锁文件 |
| 探端口时通时不通 | `curl` 走了代理。探本机一律加 `--noproxy '*'` |
| 命令里 `node` / `python` 不是想要的那个版本 | 用受管运行时全路径（本机：Node 22.22.2 与 Python 3.13.12 各在受管目录下） |
| 某些外网域名连不上 | 本机有代理（默认端口随配置变），推 git 或拉依赖失败时按需挂代理 |

---

## 可续机制（断开之后怎么接上）

**不建跨会话状态文件**，靠现场自检定位断点：

```bash
git log --oneline -5                 # 已提交到哪一步
git status --porcelain               # 有没有未提交的改动
docker ps --format '{{.Names}}'      # 数据库在不在跑
bash scripts/check-doc-links.sh      # 文档守卫绿不绿
ls docs/worklog/                     # 上一份工作台写到哪了
```

对照六阶段表就能判断「上次停在哪」。

---

## 衔接段：两处「提示式触发」

**统一为一种仪式**：AI 打总结 + 给可直接复制的触发串，**等用户手动触发**；AI 不自动调、不催促。
推迟或跳过都允许（跳过只在总结里记一笔，不纠缠）。停在这里算自然断点，把「等待触发」写进 worklog。

### 衔接一 · 初始化 → 需求打磨

初始化完成（CI 首绿）后，AI 的总结里要有这段要点：

> ✅ 初始化完成（本地跑通 / 门禁全绿 / 已入库 / CI 首绿）。
> 下一步是**需求打磨**——由 grill-with-docs 做。
> 它是手动触发的：发一句 `@skill:grill-with-docs` 接上即可；想先收工就停在这（可续），想跳过说一声。

⚠️ **不要改 `grill-with-docs` 的任何文件**（尤其它的 `disable-model-invocation` 标志）——
「提示 + 手动触发」这个设计正是以那个标志为前提的。

### 衔接二 · 需求打磨 → 产品与设计

grill 完成后同款提示（`@skill:impeccable`）。这一步的范围：

- **当场只做 `init`**——把 `PRODUCT.md` 从空占位写实；
- **`document`（`DESIGN.md`，从现有代码派生）后置到「第一个界面成型之后」**再跑。
  剧本里要写明这个后续触发点，别在骨架阶段跑（那时没东西可派生）。

### 收尾 · 开工提示

全部完成后给「下一步」建议：按 `docs/requirements/scope.md` 挑**最小的一个功能**，
走一遍完整链路（需求 → ADR → 实现 → 测试 → 提交），把这套规矩真正跑一遍。

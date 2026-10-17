# ${PROJECT_NAME}

> 一句话：这个项目是干什么的（**填这里**）。

## 它解决什么问题

<!-- 两三句：给谁用、解决什么、现在做到哪一步。写清楚「不是什么」同样重要。 -->

## 跑起来（本机开发）

基础门禁只需要 JDK 21、Maven 3.9+、Node 22 和 Python 3.11+；
本地前后端联通还需要一个可访问的 MySQL 8。Docker Compose 只是启动本机 MySQL 的推荐方式，
不是所有验证的硬前置。

### 路径 A：用 Docker 启动本机 MySQL

```bash
# 1. 复制样例并填本机值（.env.example 入库，.env 不入库）
cp .env.example .env
# 至少把 MYSQL_ROOT_PASSWORD 和 JWT 密钥换成随机值

docker compose -f docker-compose.dev.yml up -d

# 2. 起后端（默认 ${BACKEND_PORT}）
cd backend && mvn -B -ntp spring-boot:run

# 3. 起前端（默认 ${FRONTEND_PORT}，/api 已代理到后端）
cd frontend && npm install && npm run dev
```

### 路径 B：使用专用外部 MySQL

没有 Docker 但有本机或远程 MySQL 时，先准备本项目专用数据库和账号，
再在启动后端的同一个 shell 里显式设置 `SPRING_DATASOURCE_URL`、`SPRING_DATASOURCE_USERNAME`、
`SPRING_DATASOURCE_PASSWORD`，以及正式或固定开发用的 `${APP_ENV_PREFIX}_JWT_SECRET`。
Flyway 启动时会对这个目标库执行迁移，勿连接生产库。

```bash
export SPRING_DATASOURCE_URL='jdbc:mysql://127.0.0.1:3306/<数据库名>?useUnicode=true&characterEncoding=utf8&useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai'
export SPRING_DATASOURCE_USERNAME='<开发账号>'
export SPRING_DATASOURCE_PASSWORD='<开发密码>'
export ${APP_ENV_PREFIX}_JWT_SECRET='<随机密钥>'
cd backend && mvn -B -ntp spring-boot:run
```

`mvn spring-boot:run` 不会自动读取 `.env`。没有设置 JWT 环境变量时，本机可以使用启动时随机兜底，
但重启后 token 会失效；正式环境必须配置随机密钥。

### 暂时没有 MySQL

仍可运行四条守卫、后端纯单测、前端 `npm run typecheck` 和 `npm run build`。
数据库迁移、后端启动、健康端点及前后端页面联通必须记录为“未验证 / 受阻”，
不能用 H2、关闭 Flyway 或假造接口返回来宣称本地全链路已跑通。获得 Docker 或专用 MySQL 后，
再按上面任一路径补做真实联通验收。

打开 `http://127.0.0.1:${FRONTEND_PORT}/` 后，首页那行来自后端接口的返回值才是「前后端通了」的肉眼判据。

## 目录

| 目录 | 是什么 |
|------|--------|
| `backend/` | Spring Boot + MyBatis-Plus + Flyway |
| `frontend/` | Vue 3 + Vite + TypeScript + shadcn-vue + Tailwind v4 |
| `docs/` | 文档体系（索引见 `docs/README.md`） |
| `scripts/` | 机械守卫脚本 |
| `deploy/` | 部署侧配置模板（可选章节生成） |

## 配置要点

- 后端配置的默认值是**本机开发兜底**，容器里由 compose 注入环境变量覆盖；宿主机直跑用 `SPRING_DATASOURCE_*` 覆盖数据库连接。
- JWT：正式环境必须配置随机密钥；本机未配置时会用启动时随机密钥，重启后 token 失效。固定开发密钥需在启动后端的 shell 中设置。
- `.env.example` 入库，`.env` 不入库；Compose 会读取 `.env`，Maven 直跑不会自动读取它。配置的真实默认值以 `backend/src/main/resources/application.yml` 与 `.env.example` 为准。

## CI 与部署

- CI（`.github/workflows/ci.yml`）：类型检查与构建、后端单测、文档守卫；这些基础门禁不要求本机 Docker。
- 部署：见 `deploy/README.md`（仅 `--with-deploy` 生成，发布流程仍使用容器）。

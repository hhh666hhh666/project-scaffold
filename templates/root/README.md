# ${PROJECT_NAME}

> 一句话：这个项目是干什么的（**填这里**）。

## 它解决什么问题

<!-- 两三句：给谁用、解决什么、现在做到哪一步。写清楚「不是什么」同样重要。 -->

## 跑起来（本机开发）

前置：JDK 21、Maven 3.9+、Node 22、Docker（只用来起数据库）。

```bash
# 1. 起数据库
docker compose -f docker-compose.dev.yml up -d

# 2. 起后端（默认 ${BACKEND_PORT}）
cd backend && mvn -B -ntp spring-boot:run

# 3. 起前端（默认 ${FRONTEND_PORT}，/api 已代理到后端）
cd frontend && npm install && npm run dev
```

打开 `http://127.0.0.1:${FRONTEND_PORT}/`，首页上那行来自后端接口的返回值是「前后端通了」的肉眼判据。

## 目录

| 目录 | 是什么 |
|------|--------|
| `backend/` | Spring Boot + MyBatis-Plus + Flyway |
| `frontend/` | Vue 3 + Vite + TypeScript + shadcn-vue + Tailwind v4 |
| `docs/` | 文档体系（索引见 `docs/README.md`） |
| `scripts/` | 机械守卫脚本 |
| `deploy/` | 部署侧配置模板（可选章节生成） |

## 配置要点

- 后端配置的默认值是**本机开发兜底**，容器里由 compose 注入环境变量覆盖。
- JWT 密钥必须换成本机随机值，见 `docs/operations/configuration.md`。
- `.env` 不入库，模板是 `.env.example`。

## CI 与部署

- CI（`.github/workflows/ci.yml`）：类型检查与构建、后端单测、文档守卫。
- 部署：见 `docs/operations/deployment.md`（可选章节，未生成则无）。

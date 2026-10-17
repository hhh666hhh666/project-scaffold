# 技术架构模板：搬了什么、不搬什么

## 一、后端（`backend/`）

**只搬通用件**。判据：这个类换一个业务域名还成不成立？成立 → 搬；只有那个项目的业务决策才需要 → 不搬。

| 搬了 | 说明 |
|---|---|
| `common/Result` `ResultCode` `PageResult` `BusinessException` `GlobalExceptionHandler` | 统一响应信封与异常处理。业务无关 |
| `config/MybatisPlusConfig` `OpenApiConfig` `WebConfig` | 分页插件、接口文档、拦截器与 CORS 白名单（白名单参数化） |
| `security/JwtUtil` `JwtInterceptor` `UserContext` | 无状态 JWT。**密钥从配置读**，且带「检测到公开的默认值就换成随机密钥」的兜底 |
| 启动类、pom、application.yml、V1 迁移占位 | 参数化 |
| `module/example/` 六件套 + `ExampleServiceTest` | **照抄样例**。`ExampleServiceTest` 是纯 JUnit，既是单测样例，又让模块测试守卫首日就绿 |

**不搬**（都是业务决策的产物，脚手架不该预设）：

| 不搬 | 它的业务味在哪 |
|---|---|
| token 版本号失效机制（`TokenVersionSource` + `user.token_version`） | 「改密码 / 退出所有设备让旧 token 立即失效」是产品决策，代价是**每个请求多一次查库**。模板保持纯无状态 JWT，需要时自己加并写 ADR |
| 账号硬删与清理 Mapper | 注销策略是产品决策 |
| 头像 data URL 处理 | 存储策略是产品决策 |
| 判分工具、Excel 导入导出 | 纯业务 |

**其他刻意的取舍**：

- `update-strategy: not_null` 这条全局配置**保留**了，并在 yml 里写了警告注释——
  它是个「`updateById` 静默跳过 null 字段」的坑，写清楚比删掉有用。
- 后端显式版本**钉死**，不写 `<latest>`；前端依赖声明是 `^` / `~` 范围，实际安装版本由初始化时
  生成的 `package-lock.json` 固定。具体版本以下面的版本表为准，不在别处重复抄写。
- 集成测试用 **Testcontainers + 真 MySQL**，不用 H2——迁移脚本是 MySQL 方言，用 H2 等于把
  「测试环境与真实环境不一致」请回来。
- `mvn test` 只跑 `*Test`（纯单元、不需要任何服务）是一条**刻意守住的约束**，靠 surefire/failsafe 的命名分工实现。

### 版本表（真相源：模板文件）

下表由 `scripts/check_consistency.py` 与模板机械比对：改模板就要改这里，反之亦然。
它只登记**明确维护**的条目；被 Spring Boot 父 POM 管理的依赖（Flyway、MySQL 驱动、Testcontainers 等）
不在这里强行写版本，也不尝试解析远程有效版本。

<!-- consistency:versions:start -->
| 标识 | 组件 | 版本 | 声明位置 |
|---|---|---|---|
| `spring-boot` | Spring Boot | `3.5.16` | `templates/backend/pom.xml` 的父 POM |
| `mybatis-plus` | MyBatis-Plus | `3.5.17` | `mybatis-plus.version` 属性 |
| `mapstruct` | MapStruct | `1.6.3` | `mapstruct.version` 属性 |
| `lombok-mapstruct-binding` | Lombok–MapStruct binding | `0.2.0` | `lombok-mapstruct-binding.version` 属性 |
| `jjwt` | jjwt | `0.12.7` | `jjwt.version` 属性 |
| `springdoc` | springdoc | `2.9.1` | `springdoc.version` 属性 |
| `jdk` | JDK | `21` | pom 的 `java.version` 与后端 JRE 镜像 |
| `node` | Node（前端构建镜像） | `22` | `templates/frontend/Dockerfile` 的 `node:22-slim` |
| `vue` | Vue | `^3.5.0` | `templates/frontend/package.json` |
| `vite` | Vite | `^6.4.3` | 同上 |
| `tailwindcss` | Tailwind CSS | `^4.3.3` | 同上；`@tailwindcss/vite` 必须同值 |
| `typescript` | TypeScript | `~5.6.0` | 同上 |
<!-- consistency:versions:end -->

## 二、前端（`frontend/`）

Vue 3 + Vite + TypeScript + Pinia + Tailwind v4 + shadcn-vue（`components.json` 已配好，
`npx shadcn-vue@latest add <组件>` 即可拉源码入库）。

- 骨架：`api/`（axios 封装 + 领域拆分）、`router/`、`stores/`、`views/`、`lib/`（`cn()`）、`styles/`、`types/`
- **Home 白页会真的调一次 `/api/example/hello` 并把返回值显示出来**——这是「前后端通了」的肉眼判据，
  不是装饰
- 门禁只有两个：typecheck 与 build。⚠️ `vite build` 走 esbuild 只剥离类型、不做检查，
  **类型错误只会被 typecheck 挡住**
- 设计体系三层见 `FRONTEND-SYSTEM.md`

## 三、Docker 与 CI

| 部件 | 取舍 |
|---|---|
| `docker-compose.dev.yml` | **只起数据库**；后端与前端在宿主机直跑（改代码不用重建镜像）。Docker 是本机 MySQL 的推荐启动方式，联通也可使用专用外部 MySQL；纯 `mvn test` 与前端门禁不需要数据库。 |
| 后端 Dockerfile | 两阶段构建（maven → JRE）。`MAVEN_MIRROR` 开关决定是否用国内源 |
| 前端 Dockerfile | **必须 glibc 基础镜像（Node 的 slim 镜像，非 alpine）**——esbuild 没有 x64-musl 官方二进制；**必须有 `.dockerignore`**，否则宿主机 `node_modules` 会被送进构建上下文 |
| `ci.yml` | 精简到「文档守卫 + 后端单测 + 前端类型检查与构建」。源项目那套（依赖扫描、Testcontainers、镜像冒烟、端到端）**不进骨架**——骨架阶段没有业务可跑 |
| `dependabot.yml` | 每周为 Maven / npm / GitHub Actions 各提升级 PR，只提案、不自动合并；基础镜像与 MySQL 镜像**不在覆盖范围**，镜像升级仍靠人判断 |
| 发布门禁 | `release.yml` 只在推 `v*` tag 时运行；升级 PR 走普通 `ci.yml`，既不拿部署 Secrets，也不会发布 |

## 四、部署章节（`--with-deploy`，默认不生成）

`release.yml`（版本门禁 → 迁移重放 → 构建推仓库 → SSH 部署）+ `docker-compose.prod.yml` +
`scripts/server-{deploy,rollback,compose}.sh` + `deploy/` 模板。

- **镜像仓库地址、服务器 IP、用户名全是占位符**，真实值由新项目自己填。
- 凭据一律走 GitHub Secrets，**模板里没有任何真密钥**。
- 部署脚本里「部署前先备份」那一步是**建议而非强制**（备份脚本不在模板里），因为它依赖各自的备份方案。
- 回滚只换代码，**不回滚数据库**——这条写在脚本注释里。

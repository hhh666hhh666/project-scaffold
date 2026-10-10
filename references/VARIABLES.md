# 变量表与参数化规则

## 占位符语法

统一 `${VAR}`。⚠️ **只有「全大写 + 下划线」的标识符会被替换**：

```python
VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
```

其余 `${...}` 一律**原样保留**。这是刻意的——生成物里到处都是真正的 `${}` 占位符：

| 生成物里的写法 | 属于谁 | 为什么不会被误伤 |
|---|---|---|
| `${demoapp.jwt.secret}` | Spring 配置键 | 含小写 |
| `${DEMOAPP_JWT_SECRET:xxx}` | Spring 环境变量占位 | 含 `:`，不匹配「纯大写标识符」 |
| `${APP_VERSION}` | compose 变量 | 不在变量表里（未知标识符原样保留） |
| `${MYSQL_ROOT_PASSWORD:?提示}` | compose 必填断言 | 含 `:?` |
| `${BASH_SOURCE[0]}` / `${1:-}` | bash | 含 `[` / 以数字开头 |
| `${java.version}` / `${lombok.version}` | Maven 属性 | 含小写与 `.` |

**复合变量**：少数场合需要「生成物里保留一个 `${}` 包裹、里面却是替换后的值」
（Spring 的 `@Value`、yml 占位符、compose 断言）。这类值**整体**放在变量里，
例如 `JWT_SECRET_YAML` 的值就是 `${DEMOAPP_JWT_SECRET:demoapp-default-…}`——
值不会被二次替换。

## 变量表

| 变量 | 含义 | 默认值 / 计算方式 | 示例（`--name demo-app`） |
|---|---|---|---|
| `PROJECT_NAME` | 项目名（kebab） | `--name`，必填 | `demo-app` |
| `APP_CLASS` | Java 类名前缀（Pascal） | 由项目名转 Pascal | `DemoApp` |
| `APP_PREFIX` | Spring 配置前缀（小写字母数字） | 项目名去掉非字母数字 | `demoapp` |
| `APP_ENV_PREFIX` | 环境变量前缀（大写） | `APP_PREFIX.upper()` | `DEMOAPP` |
| `PACKAGE` | Java 包名 | `--package`，默认 `com.example.<APP_PREFIX>` | `com.example.demo` |
| `PACKAGE_PATH` | 包路径 | `PACKAGE.replace('.', '/')` | `com/example/demo` |
| `VERSION` | 初始版本 | `--version`，默认 `0.1.0` | `0.1.0` |
| `BACKEND_PORT` | 后端端口 | `--backend-port`，默认 `8080` | `8080` |
| `FRONTEND_PORT` | 前端 dev 端口 | `--frontend-port`，默认 `5173` | `5173` |
| `WEB_PORT` | prod 里 web 映射到宿主的端口 | `--web-port`，默认 `8081` | `8081` |
| `DB_NAME` | 数据库名 | `--db`，默认由项目名派生 | `demo_app` |
| `LINK_CHECK_SCRIPT` | 链接守卫脚本名 | `check-doc-links.sh` | |
| `TODO_ARCHIVE_SCRIPT` | 待办归档守卫脚本名 | `check-todo-archive.sh` | |
| `MODULE_TEST_SCRIPT` | 模块测试守卫脚本名 | `check-module-tests.sh` | |
| `VERSION_SCRIPT` | 版本守卫脚本名 | `check-version.sh` | |

**复合变量**（值里自带 `${...}`）：

| 变量 | 生成后的样子 |
|---|---|
| `JWT_DEFAULT_SECRET` | `demoapp-default-jwt-secret-please-replace-in-production-0123456789abcdef` |
| `CONFIG_VERSION_ANNOTATION` | `${demoapp.version:dev}` |
| `CORS_ANNOTATION` | `${demoapp.cors.allowed-origins:}` |
| `JWT_SECRET_ANNOTATION` | `${DEMOAPP_JWT_SECRET}` |
| `JWT_EXPIRE_ANNOTATION` | `${DEMOAPP_JWT_EXPIRE_DAYS:7}` |
| `JWT_SECRET_YAML` | `${DEMOAPP_JWT_SECRET:demoapp-default-…}` |
| `APP_VERSION_YAML` | `${DEMOAPP_VERSION:dev}` |
| `CORS_YAML` | `${DEMOAPP_CORS_ALLOWED_ORIGINS:}` |
| `JWT_EXPIRE_YAML` | `${DEMOAPP_JWT_EXPIRE_DAYS:7}` |
| `JWT_SECRET_ASSERT` | `${DEMOAPP_JWT_SECRET:?请在 .env 里设置 DEMOAPP_JWT_SECRET}` |
| `JWT_EXPIRE_COMPOSE` | `${DEMOAPP_JWT_EXPIRE_DAYS:-7}` |
| `CORS_COMPOSE` | `${DEMOAPP_CORS_ALLOWED_ORIGINS:-}` |

## 文件名里的占位符

路径同样会被渲染，所以模板里可以出现这样的路径：

```
templates/backend/src/main/java/${PACKAGE_PATH}/common/Result.java
templates/backend/src/main/java/${PACKAGE_PATH}/${APP_CLASS}Application.java
templates/scripts/${LINK_CHECK_SCRIPT}
```

## 校验规则

- 项目名必须 `^[a-z][a-z0-9-]*$`（它同时是 npm 包名、compose 项目名、容器名前缀）。
- 包名必须 `^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$`。

## 目录映射

| 模板子目录 | 落到目标 | 开关 |
|---|---|---|
| `root/` | 仓库根 | 总是 |
| `rules/` | `.codebuddy/rules/` | 总是 |
| `commands/` | `.codebuddy/commands/` | 总是 |
| `docs/` | `docs/` | 总是 |
| `backend/` | `backend/` | 总是 |
| `frontend/` | `frontend/` | 总是 |
| `ci/` | `.github/workflows/` | 总是 |
| `docker/` | 仓库根 | 总是 |
| `scripts/` | `scripts/` | 总是 |
| `testing/` | `docs/testing/` | `--with-testing` |
| `ops/` | `docs/operations/` | `--with-ops` |
| `deploy/` | 仓库根（内含 `.github/`、`scripts/`、`deploy/` 三段） | `--with-deploy` |

生成后恒定存在的目录（空的补 `.gitkeep`）：`docs/adr`、`docs/design`、`docs/development`、
`docs/operations`、`docs/requirements`、`docs/testing`、`docs/todo/archive`、`docs/worklog`。

# API

**目的**：讲清「真实接口在哪看」与通用约定。

**读者**：对接接口或改 Controller 的人。

**真相源**：**接口清单以运行时为准**（springdoc 与各 Controller）。本文档**刻意不维护 endpoint 表**——那类清单必然与代码漂开。

## 怎么看真实接口

启动后端后打开接口文档页（路径见 `backend/src/main/resources/application.yml` 的 `springdoc` 段），或用 `/v3/api-docs` 拿原始 JSON。

## 通用响应信封

所有接口统一返回同一个信封：`{ code, message, data, timestamp }`。

- `code = 0` 表示成功，其余见 `ResultCode` 枚举（后端 `common/ResultCode.java`）。
- 分页接口的 `data` 是 `PageResult`：`{ list, total, page, size }`。
- **字段名与错误码以代码为准**，本文不复制清单。

## 错误约定

- 业务失败抛 `BusinessException`（带业务码），由全局异常处理器转成信封。
- 参数校验失败统一 `400`，message 里带字段名。
- 未预期异常统一 `500`，响应里不暴露堆栈。

## 鉴权与数据边界

- 除白名单路径外的 `/api/**` 需要 `Authorization: Bearer <token>`。
- 白名单与跨域策略见后端 `config/WebConfig.java` 的注释。
- ⚠️ **路由层只挡「没登录」，不挡「没有数据权限」**：越权（拿别人的 id 来读写）必须由服务端判定，并在接口层测试里断言它会失败。

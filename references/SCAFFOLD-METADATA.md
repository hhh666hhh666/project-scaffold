# `.scaffold.json`：生成来源与参数记录

新项目根目录的 `.scaffold.json` 记录**最近一次完整成功的脚手架生成**。它默认生成、建议随项目入库，
用于回答「这个骨架从哪来、当时选了什么」，**不是**项目当前配置的真相源，也不是升级依据。

## 一、保证什么

- 记录生成时的项目参数：名称、包名、初始版本、数据库名、三个端口、额外模块、三个可选章节。
- 记录脚手架自身的来源：完整 Git 提交（能识别时）与生成器/模板是否有本地改动。
- 参数取**解析后的实际值**：默认包名、默认数据库名、去重后的模块列表、整数端口、布尔开关。
- 不记录：绝对输出目录、用户名、主机名、环境变量、Git remote、凭据、时间戳、命令行原文、`--force` / `--dry-run`。

## 二、不保证什么

- 不表示项目现在仍与模板一致；生成后的业务修改不会被追踪。
- 不表示初始化完成、数据库连通、CI 已绿。
- 不代表当前项目版本；新项目版本看 `frontend/package.json`、`backend/pom.xml` 与 Git tag。
- 不是外部 skill 的安装记录；那看 skill 目录自己的 `.fetched.json`。
- `--force` 重新生成不会删除旧文件；记录只说「这次生成了什么」，不是目录现状清单。

## 三、结构

```json
{
  "schema_version": 1,
  "generator": {
    "name": "project-scaffold",
    "source": {
      "commit": "49dd158d1076134a641b33efb035946536778336",
      "dirty": false,
      "status": "git"
    }
  },
  "project": {
    "name": "demo-app",
    "package": "com.example.demoapp",
    "initial_version": "0.1.0",
    "database": "demo_app",
    "ports": { "backend": 8080, "frontend": 5173, "web": 8081 },
    "modules": ["order", "product"],
    "switches": { "deploy": false, "ops": false, "testing": true }
  }
}
```

- `schema_version`：记录格式版本，不是脚手架版本或项目版本。
- `generator.source.status`：`git` 表示识别成功，`unknown` 表示无法确认来源。
- `generator.source.commit`：完整提交号；无法确认时为 `null`，不伪造版本号。
- `generator.source.dirty`：只检查 `scripts/scaffold.py` 与 `templates/`；`null` 表示状态未知。
- `project.initial_version`：生成时给新项目的初始版本，不是当前发布版本。

## 四、来源识别规则

只承认「Git 仓库根**恰好是这份脚手架的根目录**」。以下情况记为 `unknown`：

- skill 是普通目录复制安装，没有 `.git`；
- 脚手架位于某个业务仓库的子目录（外层仓库的提交不会被误记）；
- 系统没有 Git、命令失败或超时；
- 仓库还没有提交。

`dirty` 只看生成器输入：

- `scripts/scaffold.py`；
- `templates/` 下的修改、暂存、删除与未跟踪文件。

改 README、测试或工作日志不会把生成器标成脏。

## 五、写入与覆盖

- `.scaffold.json` 进入与文本 / JSON dry-run 相同的文件清单，预览与实际生成一致。
- 记录在模板与 `.gitkeep` 全部写完后**最后原子发布**；中途失败不会更新旧记录。
- 已有记录无法解析、格式不受支持或缺少 `project-scaffold` 标识时，即使 `--force` 也拒绝覆盖。
- `--force` 完整成功后，记录更新为本次生成；旧记录留在项目 Git 历史里。
- 不使用整个目录的事务或回滚；失败时可能留下部分文件，此时不能把旧记录当成目录现状。

## 六、怎么读

排查「这个项目从哪版骨架开始」时：

1. 看 `generator.source.commit` 与 `dirty`；
2. 看 `project` 里的参数是否与当前配置一致；
3. 需要更早的记录时看项目 Git 历史中的这个文件。

不要用它与当前模板做自动比对，也不要据此覆盖业务代码。模板是否仍兼容，需要人工判断。

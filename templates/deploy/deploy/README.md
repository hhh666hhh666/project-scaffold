# 部署侧配置模板

这里放**要传到服务器上、但不随镜像走**的东西：宿主反代的站点配置、云端环境变量样例。

**不在这里的东西**：compose 编排（`docker-compose.prod.yml` 在仓库根）、部署脚本（`scripts/server-*.sh`）、
发布流水线（`.github/workflows/release.yml`）——它们由发布流程自动送到服务器，不需要手工传。

## 首次上线前的准备清单

1. **镜像仓库**：建好命名空间，拿到**用户名与固定密码**（不是 AccessKey——个人版镜像仓库通常不支持 AccessKey 推送）。
2. **服务器**：装好容器运行时；确认 80/443 上的对外入口归谁管（若已有面板或反代，就让它反代到本项目的 web 端口，别抢端口）。
3. **仓库 Secrets**：`ACR_USERNAME` / `ACR_PASSWORD` / `DEPLOY_SSH_KEY` / `DEPLOY_SSH_KNOWN_HOSTS`（后两个可选但推荐）。
4. **服务器上的 `.env`**：照 `.env.cloud.example` 填好，放在 `/srv/${PROJECT_NAME}/.env`。**这个文件不入库**。
5. **数据库**：绑到宿主机上的绝对路径（`MYSQL_DATA_DIR`），**不要放在容器里**——容器删了数据不能跟着没。

## 怎么传

发布流水线每次部署都会把 compose 与脚本 scp 到 `/srv/${PROJECT_NAME}/compose/`。
本目录下的两份模板只在**首次**手工传一次：

```bash
scp deploy/.env.cloud.example  <user>@<host>:/srv/${PROJECT_NAME}/.env   # 然后改真值
scp deploy/nginx/site.conf.example <user>@<host>:/etc/nginx/conf.d/<site>.conf
```

## 回滚

```bash
cd /srv/${PROJECT_NAME}/compose/scripts
bash server-rollback.sh            # 回到上一个已上线版本
bash server-rollback.sh 1.0.3      # 或显式指定
```

⚠️ **回滚只换代码，不回滚数据库**——迁移是不可逆的，所以部署前必须先备份。

## 备份与恢复

`server-deploy.sh` 在启动新版本之前会调用 `scripts/backup-mysql.sh`；备份失败会中止部署。
脚本会随发布流水线一起送到服务器，不需要手工传。

- **位置**：默认 `/srv/${PROJECT_NAME}/backups/`，可用 `BACKUP_DIR` 覆盖；
- **命名**：`<库名>-<年月日-时分秒>-<版本>.sql.gz`；
- **保留**：默认最近 7 份，可用 `BACKUP_KEEP` 覆盖；部署前会打印清理了哪些旧文件；
- **手动执行**：`cd /srv/${PROJECT_NAME}/compose/scripts && ENV_FILE=/srv/${PROJECT_NAME}/.env bash backup-mysql.sh`。

恢复前先停掉后端，避免恢复过程中继续写入：

```bash
docker stop <项目名>-server
gunzip -c /srv/<项目名>/backups/<备份文件>.sql.gz \
  | docker exec -i <项目名>-mysql mysql -uroot -p <库名>
docker start <项目名>-server
```

⚠️ 这是**本机备份**：防误操作、坏迁移和容器误删，**不防磁盘损坏**。
异地或对象存储备份需要按自己的基础设施另配。

# iCore Agent 生产部署

本文说明如何使用 Docker Compose 部署 iCore Agent。生产 Compose 只管理应用、网关、后台任务和初始化任务；PostgreSQL、Redis、MinIO、Kafka 与 ClickHouse 需要由部署环境预先提供。

## 网络模型

生产容器使用两个 bridge 网络：

- Compose 默认网络用于应用容器之间通信，并作为访问模型服务和第三方 API 的默认出口。
- `infra-access` 是预先创建的 external internal bridge，仅用于连接基础设施服务。

默认外部网络名是 `project-icore-agent-infra-access`，可通过 `ICORE_INFRA_ACCESS_NETWORK_NAME` 修改。创建默认网络的命令如下：

```bash
docker network create \
  --driver bridge \
  --internal \
  project-icore-agent-infra-access
```

基础设施容器必须接入同一个外部网络，并提供以下网络 alias 和标准容器端口：

| Alias | 端口 | 用途 |
| --- | --- | --- |
| `postgres` | `5432` | Agent 与支付数据库 |
| `redis` | `6379` | 会话和网关限流 |
| `minio` | `9000` | 对象存储内部 API |
| `kafka` | `9092` | 日志和支付事件 |
| `clickhouse` | `8123`、`9000` | 日志查询和迁移 |

外部网络只能连接同一个 Docker Engine 中的容器。跨服务器部署时应使用可路由的内网 DNS 地址替换上述 alias，不能依赖 Docker bridge。

## 准备配置

进入后端目录并从样例创建生产配置：

```bash
cd icore-agent
for example in dotenv/production/.env.*.example; do
  cp "$example" "${example%.example}"
done
```

逐个替换所有 `<replace-with-...>` 占位值，并重点确认：

- `.env.app` 中的 `ICORE_INFRA_ACCESS_NETWORK_NAME` 与预创建网络一致。
- `.env.database`、`.env.memory`、`.env.kafka`、`.env.clickhouse` 和 `.env.minio` 使用外部网络内可解析的地址。
- `.env.gateway` 中配置实际前端来源；默认 `GATEWAY_PORT_BIND=127.0.0.1:11000:11000`，仅允许同机反向代理访问。
- `.env.minio` 中 `MINIO_INTERNAL_ENDPOINT` 面向容器网络，`MINIO_PUBLIC_ENDPOINT` 必须是浏览器或 API 调用方能够访问的 HTTPS 地址。
- `.env.auth`、`.env.storage`、`.env.logging` 和 `.env.payment` 使用独立的生产密钥，不复用样例值。

生产 dotenv 文件包含密钥，不得提交到 Git。

## 部署

先检查 Compose 合并结果。该命令不会要求外部网络已经存在：

```bash
./scripts/compose.sh production config
```

确认基础设施服务已经启动并接入外部网络后，构建并启动应用：

```bash
./scripts/compose.sh production up -d --build
```

启动过程会执行 MinIO bucket 初始化、Kafka topic 初始化、ClickHouse migration 和支付数据库 migration。任一初始化任务失败时，不应绕过依赖直接启动后续服务，应先查看对应任务日志并修复基础设施连接或权限。

查看状态和日志：

```bash
./scripts/compose.sh production ps
./scripts/compose.sh production logs --tail=200
```

验证 Gateway 健康状态：

```bash
curl --fail http://127.0.0.1:11000/health
```

反向代理应将业务 API 流量转发到 `http://127.0.0.1:11000`，并负责公网 TLS。除非部署环境明确需要直接暴露 Gateway，否则不要把端口绑定改成 `0.0.0.0`。

## 升级与停止

部署新版本时重新构建并复用现有配置：

```bash
./scripts/compose.sh production up -d --build
./scripts/compose.sh production ps
```

停止并删除应用容器：

```bash
./scripts/compose.sh production down
```

`down` 不会删除 external 基础设施网络，也不会停止外部基础设施服务。日志服务的本地 spool 和工具工作区使用 Compose volume；执行带 `--volumes` 的清理命令前必须先确认数据保留要求。

## 故障检查

- 启动提示缺少基础设施网络：核对 `.env.app` 网络名，并使用 `docker network inspect <network>` 检查网络。
- 容器无法解析基础设施 alias：确认对应基础设施容器已接入 external 网络并配置正确 alias。
- Kafka 客户端连接后跳转到不可达地址：检查 broker advertised listener，容器网络 listener 应向客户端发布 `kafka:9092`。
- 上传成功但浏览器无法读取对象：检查 `MINIO_PUBLIC_ENDPOINT` 是否为客户端可访问地址，而不是 `minio:9000`。
- 内部 HTTP 请求经过代理：确认运行时 `NO_PROXY` 和 `no_proxy` 保留项目服务名与基础设施 alias。

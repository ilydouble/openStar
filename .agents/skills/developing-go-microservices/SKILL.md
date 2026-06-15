---
name: developing-go-microservices
description: 指导在 openStar/icore-agent 中开发、重构或评审 Go 微服务：优先复用 services/lib-go 的 envconfig、http/api、http/headers、http/server、mq/kafka、logging 等公共能力；避免重复实现已有公共代码；判断何时将跨服务通用能力上移到 lib-go；设计服务自治数据库时使用 scripts/db-bootstrap.sh 初始化数据库/角色/权限，并用服务本地 migrations/ 与 golang-migrate 管理表结构迁移。Use when Codex is asked to add, refactor, review, or design Go microservices, lib-go reuse, HTTP contracts, Kafka/logging shared helpers, or service-owned PostgreSQL migrations in this repo.
---

# Developing Go Microservices

## 目标

在 `icore-agent/src/icore_agent/services/` 下开发 Go 微服务时，先复用 `lib-go`，再写服务自己的代码。只有服务领域内的业务规则、Repository、外部供应商适配器、HTTP handler 编排、数据库 schema 和迁移属于具体微服务。

## 开发流程

1. 先定位目标服务和 `lib-go` 当前代码，使用 `rg --files icore-agent/src/icore_agent/services/lib-go` 查看已有公共能力。
2. 对照复用清单删除服务内重复 helper。服务可以保留薄包装，但不要复制公共实现。
3. 新增能力前判断它属于服务领域还是跨服务基础设施。跨服务能力优先放入 `lib-go` 并配套单元测试。
4. 服务入口只做 wiring：加载配置、创建 Repository/客户端、组装 router、启动 server、注册 graceful shutdown。
5. 任何数据库访问都放在 Repository 或基础设施层；不要在 HTTP handler 中写临时 SQL。
6. 修改后运行聚焦测试，再运行服务目录下的 `go test ./...`，涉及 Compose 或迁移时再跑 `./compose.sh config ...`。

## lib-go 复用清单

- `envconfig`：读取 `string`、`duration`、`int`、`int64`、`bool`、CSV 环境变量。服务配置包应调用它，不要重复写 `os.Getenv` 解析器。
- `http/api`：复用 `ApiEnvelope`、`WriteJSON`、`WriteError`、`DecodeJSONWithOptions`、`DecodeJSONStrict`、`TokenAuth`、`NewRouter`。HTTP JSON 合同和 router 基础类型不要在服务内重新定义。
- `http/headers`：复用 `X-Request-ID`、`X-User-ID`、`X-User-Roles`、`X-Forwarded-For`、`X-Real-IP` 常量和 `ClientIP`。网关可信请求头的名称不能在服务里散落字符串。
- `http/server`：复用带超时配置的 `server.New` 创建 `net/http.Server`。不要在每个服务里手写一份超时 server 初始化。
- `mq/kafka`：复用 `KafkaPublisher`、`Config`、`Message`、`Check`、`Publish`、`Close`。服务只负责序列化自己的领域事件和 outbox 状态机。
- `logging`：复用 logging-service 合同、`LoggingServiceClient` 和 `AppLogger`。服务日志事件字段不要另起一套结构。

## 上移到 lib-go 的标准

把代码上移到 `lib-go` 前，确认它满足这些条件：

- 至少两个 Go 服务会用，或者明显是 HTTP、headers、env、Kafka、logging、server 这类服务无关基础设施。
- API 不包含支付、存储、网关、供应商名称等服务领域词。
- 行为稳定，可用小单元测试覆盖，且不会强迫所有服务引入不必要依赖。
- 包名按能力边界放置，例如 `http/api`、`http/headers`、`mq/kafka`，不要放成泛化的 `utils`。

这些内容不要上移：

- 服务自己的业务错误枚举、业务状态机、支付/存储/账号领域模型。
- 供应商字段和协议适配，例如微信支付 payload、回调验签细节。
- 只被一个服务使用且抽象不稳定的便捷函数。需要时先留在服务内。

## 微服务结构规范

使用 DDD 分层组织 Go 服务：

- `cmd/<service>/main.go`：进程入口和依赖组装。
- `internal/config`：服务配置，复用 `lib-go/envconfig`。
- `internal/domain`：领域模型、值对象、领域错误。
- `internal/application`：用例编排，不依赖 HTTP 框架。
- `internal/infrastructure`：PostgreSQL、Kafka、外部供应商客户端等实现。
- `internal/interfaces/http/v1`：HTTP adapter、handler、request/response DTO。
- `migrations/`：服务本地 `golang-migrate` SQL 文件。
- `scripts/db-bootstrap.sh`：服务数据库、角色、schema、权限的初始化入口。

HTTP handler 只做认证上下文读取、请求 decode、调用 application service、写 envelope 响应。Repository 接口放在领域或应用需要的位置，实现放在 infrastructure。

## 数据库开发方式

Go 微服务拥有独立数据库时，采用服务自治模式：

1. 创建 `scripts/db-bootstrap.sh`，使用 admin 连接等待 PostgreSQL 可用。
2. 在 bootstrap 中创建或更新服务数据库角色，设置 `LOGIN` 密码和最小权限。
3. 创建服务数据库，撤销 `PUBLIC` 默认权限，仅授予服务角色必要连接权限。
4. 创建服务 schema 并将 owner 设置为服务角色，配置数据库 `search_path`。
5. 表、索引、约束、触发器等结构变化只写入服务本地 `migrations/*.up.sql` 和 `*.down.sql`。
6. 使用 `golang-migrate` 执行迁移；不要为 Go 服务自有数据库新增 Python Alembic migration。
7. Compose 中通常拆出 `<service>-db-migrate` 或 bootstrap/migrate 容器，业务服务依赖迁移完成后再启动。

迁移文件要可审查、可回滚，命名使用递增编号，例如 `000001_create_orders.up.sql` 和 `000001_create_orders.down.sql`。不要把业务服务运行时账号授予其他应用写权限。

## Docker 与 Compose

Go 服务引入 `lib-go` 后，检查 Docker build context 是否能同时包含目标服务目录和 `services/lib-go`。如果原 Dockerfile 只以单个服务目录为 context，需在 Compose 中扩大 context 或调整 `COPY` 路径，并把这一项列入实现计划。

服务环境变量放在对应的 `.env.<domain>.example` 或既有服务 env 示例中，保留占位符，不提交真实 `.env`。通过 `icore-agent/compose.sh` 验证 Compose 展开结果。

## 验证清单

- 运行 `gofmt` 格式化所有改动的 Go 文件。
- 运行目标服务的聚焦测试，再运行该服务目录下的 `go test ./...`。
- 改了 `lib-go` 时，同时运行 `lib-go` 自身测试和至少一个调用方服务测试。
- 改了数据库迁移、bootstrap 或 Compose 时，运行 `./compose.sh config <service>` 或相关服务组合。
- 检查 `git diff --check`，确认没有空白错误。

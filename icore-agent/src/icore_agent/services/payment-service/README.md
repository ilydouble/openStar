## 支付模块启动说明

### env文件
编辑 icore-agent/dotenv/dev/.env.payment 或 icore-agent/dotenv/production/.env.payment, 一共有这些参数
- POSTGRES_ADMIN_USER=icore_agent # bootstrap.sh 创建支付db时使用的高权限用户, 默认为 icore_agent
- POSTGRES_ADMIN_PASSWORD=change-me # bootstrap.sh 创建支付db时使用的高权限用户密码
- POSTGRES_ADMIN_DB=icore_agent_db # PostgreSQL 连接需要先连上已有数据库
- PAYMENT_DB_HOST=postgres # docker compose里面的 service name, 如果以后使用 host 模式, 这里填 host 地址
- PAYMENT_DB_PORT=5432 # docker compose里面数据库容器的容器内端口, 若以后使用 host 模式, 填写 host 端口
- PAYMENT_DB_USER=icore_payment # 为支付服务创建的数据库用户
- PAYMENT_DB_PASSWORD=<replace-with-payment-db-password> # 支付服务的数据库用户密码
- PAYMENT_DB_NAME=icore_payment_db # 支付服务的 db 名
- PAYMENT_DB_SCHEMA=payment # 支付服务的 schema
- PAYMENT_DATABASE_URL=postgres://icore_payment:<replace-with-payment-db-password>@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment # 支付服务URL, 上面填了这里可以不填
- PAYMENT_SERVICE_ADDR=:8080 # 支付服务地址
- PAYMENT_KAFKA_BROKERS=kafka:9092 # 支付服务要连接的 Kafka Brokers 地址, 这里默认 kafka在 compose 内部, 用服务名访问 
- PAYMENT_KAFKA_TOPIC=icore.events.payment.v1 # 支付服务在 Kafka 中占有的 topic
- PAYMENT_KAFKA_CHECK_TIMEOUT=10s # 支付服务的 Kafka 检查超时时间
- PAYMENT_LOGGING_SERVICE_NAME=payment-service # 支付服务在向日志服务发送消息时使用的服务名
- PAYMENT_LOGGING_SERVICE_TIMEOUT=2s # 支付服务向日志服务发送消息时的超时
- PAYMENT_LOGGING_QUEUE_SIZE=4096 # 支付服务向日志服务发送消息时的队列容量
- PAYMENT_ORDER_TTL=30m # 支付订单超时
- PAYMENT_OUTBOX_POLL_INTERVAL=2s
- PAYMENT_OUTBOX_BATCH_SIZE=50 # outbox publisher 每轮从 payment_outbox 里 claim 多少条待发布事件
- PAYMENT_OUTBOX_PUBLISH_TIMEOUT=10s # outbox 发布 kafka 超时
- PAYMENT_CATALOG_JSON_PATH=/etc/icore/payment-service/catalog/plan_items.json # 现有的 Plan 的信息json路径, 商品较少, 使用 json 存, 支付服务启动时读取
- WECHATPAY_APP_ID=<replace-with-wechatpay-app-id> # 微信支付商家申请的 APP_ID
- WECHATPAY_MCH_ID=<replace-with-wechatpay-merchant-id> # 微信支付的商家ID
- WECHATPAY_MCH_CERT_SERIAL_NO=<replace-with-merchant-certificate-serial-no> # 微信支付商家证书序列号
- WECHATPAY_MCH_PRIVATE_KEY_PATH=/etc/icore/payment-service/wechatpay/secrets/apiclient_key.pem # 微信支付商家apiclient私钥路径, 这里是容器内部路径, 
在宿主机应放在 catalog/wechatpay/secrets/, 容器构建时会进行复制
- WECHATPAY_API_V3_KEY=<replace-with-api-v3-key> # 32位微信支付 APIv3 Key
- WECHATPAY_PUBLIC_KEY_ID=<replace-with-wechatpay-public-key-id> # 微信支付公钥 Key ID
- WECHATPAY_PUBLIC_KEY_PATH=/etc/icore/payment-service/wechatpay/public/wechatpay_public_key.pem # 微信支付公钥路径, 这里是容器内部路径,
在宿主机应放在 catalog/wechatpay/secrets/, 容器构建时会进行复制
- WECHATPAY_NOTIFY_URL=https://<replace-with-public-domain>/webhooks/wechatpay/native # 微信支付通知回调URL, 必须是一个公网可达地址, 必须使用 HTTPS, 本地调试可以通过 cloudflared 临时获取
- WECHATPAY_API_HOST= # 微信支付域名, 这里使用了 Go SDK, 可不填
- WECHATPAY_HTTP_TIMEOUT=10s # 微信支付HTTP超时
- WECHATPAY_REQUIRE_PRODUCTION_HOST=false # 是否强制微信支付 API host 必须是官方生产域名, 如果是 true 只要 WECHATPAY_API_HOST 非空，就必须等于微信支付 SDK 的生产API server，否则 payment-service 启动失败

### 注意
本地测试时, 每次申请cloudflared隧道之后, 都更新参数 WECHATPAY_NOTIFY_URL 并 build 一次 payment-service

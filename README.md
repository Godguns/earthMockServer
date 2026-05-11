# earthMockServer

基于 `Python + FastAPI + PostgreSQL + SQLAlchemy` 的生活模拟 / 虚拟社会游戏后端初始架构。

当前已经落地的能力：

- 用户注册、登录、JWT 鉴权
- 人格设定存储接口
- 可同时服务“通知中心”和“聊天流”的消息事件模型
- 支持随机 NPC 推送和特定事件触发推送
- 内置可替换的 AI 消息生成服务占位层

## 项目结构

```text
app/
  api/           FastAPI 路由与依赖
  core/          配置与安全
  db/            数据库连接与初始化
  models/        SQLAlchemy 模型
  schemas/       Pydantic 请求/响应模型
  services/      业务逻辑与调度
tests/           最小测试
```

## 快速开始

1. 启动 PostgreSQL

```bash
docker compose up -d
```

2. 创建环境变量

```bash
copy .env.example .env
```

3. 安装依赖

```bash
pip install -e .[dev]
```

4. 启动服务

```bash
uvicorn app.main:app --reload
```

服务启动后会自动建表。

## 核心接口

### 认证

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### 人格设定

- `GET /api/v1/persona/me`
- `PUT /api/v1/persona/me`

前端可以将人物设定、说话风格、喜欢的话题、边界、原始 JSON 配置等一起传入 `raw_settings` 和结构化字段中。

### 消息系统

- `GET /api/v1/messages`
- `POST /api/v1/messages/trigger/random`
- `POST /api/v1/messages/trigger/event`
- `POST /api/v1/messages/{message_id}/read`

说明：

- `channel=notification` 用于前端通知中心
- `channel=chat` 用于聊天流
- 随机推送会自动同时写入两个渠道
- 事件推送支持立即投递或通过 `scheduled_for` 延迟投递

## 后续建议

这版是一个可继续扩展的第一阶段骨架。下一步很适合继续补：

- Alembic 数据迁移
- 真正的 LLM/NPC 对话生成接入
- 会话 / 好感度 / 世界状态等游戏系统
- WebSocket 或 SSE 实时推送

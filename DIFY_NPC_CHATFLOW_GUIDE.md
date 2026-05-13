# Dify NPC Chatflow 搭建教程与指导手册

这份手册面向当前 `earthMockServer` 项目，目标是帮你把游戏里的 NPC 接到 Dify Chatflow，并且知道：

- 后端现在已经具备哪些 Dify 能力
- Dify 平台上应该怎么建 Chatflow
- 当前项目推荐怎样组织输入输出
- 怎么测试
- 怎么新增下一个 NPC

## 1. 当前项目现状

当前代码里，已经具备这些 Dify 相关基础能力：

- Dify 请求封装：`app/services/dify_chat_service.py`
- NPC 配置定义：`app/services/npc_profiles.py`
- 母亲 NPC 的输入构造：`build_mother_dify_inputs(...)`
- 母亲 NPC 的主动消息 query 构造：`build_mother_proactive_query(...)`
- 母亲 NPC 的回复 query 构造：`build_mother_reply_query(...)`

当前只定义了一个可接 Dify 的 NPC：

- `mother`

同时，后端现在已经支持把 NPC 上下文打包成单个 JSON 字符串传给 Dify：

- `inputs.raw_inputs`

这意味着你在 Dify 开始节点里，只需要配 1 个输入变量：

```text
raw_inputs
```

## 2. 当前要特别注意的地方

虽然 Dify 基础工具和输入构造已经有了，但“消息路由真正调用 Dify”这一步目前还没有完全切过去。

也就是说，当前代码状态是：

- Dify service 已经有
- mother NPC 输入构造已经有
- mother NPC query 构造已经有
- 但 `/messages/reply` 目前还是占位 ACK 逻辑
- `trigger/random` 目前还是本地 `NarrativeAIService` 假数据逻辑

所以这份手册重点是先把 Chatflow 应用本身搭好、测通。后面如果你要把线上消息正式切到 Dify，再把调用链路接过去即可。

## 3. 相关文件总览

后端根目录下，和 Dify 最相关的文件如下：

- `app/services/dify_chat_service.py`
- `app/services/npc_profiles.py`
- `app/core/config.py`
- `.env.example`
- `docs/dify/README.md`
- `docs/dify/mother_chatflow_setup.md`
- `docs/dify/test_inputs/mother_inputs_object.json`
- `docs/dify/test_inputs/mother_chat_messages_payload.json`

推荐先看：

1. 本文档
2. `docs/dify/mother_chatflow_setup.md`
3. `docs/dify/test_inputs/*.json`

## 4. 整体架构怎么理解

在这个项目里，Dify Chatflow 的职责是：

1. 接收后端传来的 `query`
2. 接收后端传来的 `inputs.raw_inputs`
3. 在代码节点中解析 `raw_inputs`
4. 组装 NPC 上下文 prompt
5. 让 LLM 生成 NPC 消息正文
6. 把最终结果包装成 JSON 字符串返回给后端

推荐的数据流：

```text
游戏前端
-> earthMockServer
-> Dify /chat-messages
-> Chatflow 开始节点
-> 代码节点解析 raw_inputs
-> LLM 节点生成 NPC 文本
-> 代码节点包装 JSON
-> earthMockServer
-> 入库 / 推送到前端
```

## 5. 环境变量配置

当前后端已经预留了 mother NPC 的 Dify 配置：

```env
DIFY_BASE_URL=http://YOUR_DIFY_HOST/v1
DIFY_TIMEOUT_SECONDS=45
DIFY_NPC_MOTHER_API_KEY=
DIFY_NPC_MOTHER_WORKFLOW_ID=
```

说明：

- `DIFY_BASE_URL`：Dify API 地址，通常以 `/v1` 结尾
- `DIFY_TIMEOUT_SECONDS`：请求超时时间
- `DIFY_NPC_MOTHER_API_KEY`：mother 这个 Chatflow 应用的 API Key
- `DIFY_NPC_MOTHER_WORKFLOW_ID`：可选，指定某个已发布的 workflow 版本

如果你不需要强制指定 workflow 版本，`DIFY_NPC_MOTHER_WORKFLOW_ID` 可以先空着。

## 6. 为什么推荐 `raw_inputs`

这个项目里，NPC 上下文字段很多。如果每加一个字段，都去 Dify 开始节点里多配一个变量，维护成本会越来越高。

所以当前项目采用的推荐方式是：

- 后端把完整玩家数据组装成一个 JSON 对象
- 再转成字符串放进 `inputs.raw_inputs`
- Dify 代码节点里只解析这一个字段

优点：

- Dify 平台只配 1 个开始输入
- 后端扩字段最方便
- 以后新增 NPC 时也能沿用同一套路

## 7. Dify 里如何新建 Chatflow

建议在 Dify 里使用：

- 应用类型：`Chatflow`

创建完成后，按下面的节点结构搭建：

```text
开始
-> 生成 NPC 上下文（代码执行）
-> 生成 NPC 消息（LLM）
-> 包装输出（代码执行）
-> 结束
```

### 7.1 开始节点

只创建 1 个输入变量：

```text
raw_inputs
```

类型：

```text
text
```

### 7.2 第一个代码节点

职责：

- `JSON.parse(raw_inputs)`
- 生成 NPC 角色设定
- 生成本次触发场景说明
- 输出 `parsed_context`

这个节点的完整可复制版本，已经放在：

- `docs/dify/mother_chatflow_setup.md`

### 7.3 LLM 节点

职责：

- 读取 `parsed_context`
- 结合 `sys.query`
- 输出一条自然的 NPC 消息正文

推荐约束：

- 只输出正文
- 不输出解释
- 不输出 JSON
- 不要加 `妈妈：` 这种前缀

### 7.4 第二个代码节点

职责：

- 接收 LLM 文本输出
- 包装成标准 JSON 字符串

推荐返回格式：

```json
{
  "title": "妈妈",
  "content": "早点睡，别又熬夜了啊",
  "should_notify": true,
  "emotion": "concerned"
}
```

### 7.5 结束节点

结束节点建议输出一个字段：

```text
answer
```

值引用“包装输出”节点的 `answer`。

## 8. 当前 mother NPC 的标准做法

目前 mother NPC 的标准配置文档已经单独整理好了：

- `docs/dify/mother_chatflow_setup.md`

你可以把它理解成“当前项目第一套可运行模板”。

如果只是先把 mother 跑起来，直接照那份配置做就够了。

## 9. 测试输入怎么用

项目里已经放了两份测试文件。

### 9.1 原始对象

文件：

- `docs/dify/test_inputs/mother_inputs_object.json`

用途：

- 看 `raw_inputs` 里原本应该有什么内容
- 方便你对照字段意义

### 9.2 完整 Dify 请求体

文件：

- `docs/dify/test_inputs/mother_chat_messages_payload.json`

用途：

- 用 Postman / curl / Dify 调试时直接复用
- 验证 `/chat-messages` 请求结构是否正确

这个文件已经按 JSON 做过解析校验。

## 10. 推荐测试流程

建议你按这个顺序测试：

1. 先在 Dify 平台手动运行 Chatflow
2. 开始节点只传 `raw_inputs`
3. 确认第一个代码节点能正常解析 JSON
4. 确认 LLM 节点能输出纯文本消息
5. 确认包装输出节点能返回 JSON 字符串
6. 确认结束节点输出的是 `answer`
7. 最后再从后端 API 去调用 Dify

如果你直接跳到后端联调，定位问题会慢很多。

## 11. 常见错误与排查

### 11.1 `Output answer is missing`

原因：

- 代码节点声明的输出变量名叫 `answer`
- 但代码里 `return` 的字段不是 `answer`

正确做法：

```javascript
return {
  answer: JSON.stringify({
    title: "妈妈",
    content,
    should_notify: true,
    emotion: "concerned"
  }, null, 2)
};
```

### 11.2 `raw_inputs` 解析失败

原因：

- 开始节点没传 `raw_inputs`
- 或者 `raw_inputs` 不是合法 JSON 字符串

建议：

- 先用项目里的 `mother_chat_messages_payload.json`
- 确保 `inputs.raw_inputs` 是字符串，不是对象

### 11.3 Dify 返回不是合法 JSON

后端当前的解析器会把 `answer` 当 JSON 读。

所以如果你让 LLM 直接返回自然语言，而不是最终 JSON 字符串，后端解析就会失败。

稳妥方案：

- 让 LLM 只输出正文
- 再用最后一个代码节点统一包装成 JSON

### 11.4 `workflow_id_format_error`

原因：

- `DIFY_NPC_MOTHER_WORKFLOW_ID` 不是合法 UUID

建议：

- 不确定时先留空
- 确认你填的是 Dify 已发布 workflow 的正确 ID

## 12. 新增一个 NPC 时怎么做

后续你要新增别的 NPC，建议按下面步骤扩展：

1. 在 `app/services/npc_profiles.py` 新增一个 `NpcProfile`
2. 给这个 NPC 增加专属的 `build_xxx_dify_inputs(...)`
3. 给这个 NPC 增加 `build_xxx_reply_query(...)`
4. 给这个 NPC 增加 `build_xxx_proactive_query(...)`
5. 在 `.env.example` 和 `app/core/config.py` 增加对应的 API Key / Workflow ID
6. 在 `docs/dify/` 下新增一份 `xxx_chatflow_setup.md`
7. 在 `docs/dify/test_inputs/` 下新增测试 JSON
8. 最后再把消息路由真正切到 Dify 调用链

建议命名风格保持一致：

- `mother_chatflow_setup.md`
- `boss_chatflow_setup.md`
- `roommate_chatflow_setup.md`

## 13. 后续真正接入线上链路时建议怎么做

如果你下一步要把当前占位逻辑替换成真实 Dify 调用，建议顺序是：

1. 先接通主动推送链路
2. 再接通玩家回复链路
3. 再补会话 ID 持久化
4. 最后再做多 NPC 扩展

更具体一点：

- `generate_random_message_for_user(...)` 里替换本地假消息逻辑
- `/messages/reply` 里替换当前 ACK 逻辑
- 利用 `npc_conversation_sessions` 持久化 `dify_conversation_id`
- 让不同 NPC 使用不同 profile / workflow / prompt

## 14. 推荐维护方式

建议以后都按“两层文档”维护：

1. 后端根目录放总手册
2. `docs/dify/` 放每个 NPC 的细化配置文档

这样有几个好处：

- 根目录文档负责讲原则和整体架构
- `docs/dify/` 负责放可复制的操作细节
- 新 NPC 来了也不会把一个文档越写越乱

## 15. 当前项目里的推荐入口

建议你以后按这个顺序查资料：

1. `DIFY_NPC_CHATFLOW_GUIDE.md`
2. `docs/dify/README.md`
3. `docs/dify/mother_chatflow_setup.md`
4. `docs/dify/test_inputs/*.json`

## 16. 结论

对这个项目来说，当前最稳的 Dify 接入方式就是：

- 用 `Chatflow`
- 开始节点只收 `raw_inputs`
- 代码节点解析 `raw_inputs`
- LLM 只生成消息正文
- 最后一个代码节点统一包装 JSON

这套方式最适合当前 Earth Online 的 NPC 设计，也最方便后续扩更多角色。

# AssistBot 设计文档

## 概述

AssistBot 是一个 Telegram 聊天机器人，帮助用户分析、梳理、总结、归纳特定 topic 的最新资讯。用户通过 Telegram 发送 topic 关键词，Bot 从多个数据源采集资讯，利用 LLM 生成结构化摘要，并支持对话式追问深挖。

## 需求摘要

- **交互方式**：Telegram Bot（架构预留扩展其他平台）
- **数据源**：免费 + 权威优先，RSS > Reddit > 网页爬取，支持 RSSHub
- **LLM**：可配置多后端（Claude、OpenAI 等），可切换
- **使用模式**：主动查询 + 对话式深挖，暂无定时推送
- **语言**：Python >= 3.11
- **部署**：先本地运行，后续再考虑
- **持久化**：SQLite 轻量持久化
- **输出语言**：统一中文（英文源内容由 LLM 翻译为中文）

## 架构

单体 Pipeline 架构，模块化设计：

```
用户发消息 → Telegram Bot(handlers) → 意图识别
  → 新查询：pipeline → sources(采集) → 预处理 → llm(摘要) → 回复
  → 追问：conversation(上下文) → llm(深入分析) → 回复
```

## 项目结构

```
AssistBot/
├── bot/                  # Telegram Bot 层
│   ├── handlers.py       # 消息处理器（命令、对话）
│   └── client.py         # Telegram Bot 初始化与启动
├── sources/              # 数据源层（统一接口）
│   ├── base.py           # 数据源抽象基类
│   ├── rss.py            # RSS 订阅源（含 RSSHub）
│   ├── reddit.py         # Reddit（JSON API）
│   └── scraper.py        # 网页爬取兜底
├── llm/                  # LLM 层（可切换后端）
│   ├── base.py           # LLM 抽象基类
│   ├── claude.py         # Claude 实现
│   └── openai.py         # OpenAI 实现
├── core/                 # 核心逻辑
│   ├── pipeline.py       # 采集 → 去重 → 摘要 主流程
│   ├── conversation.py   # 对话上下文管理
│   └── topics.py         # Topic 配置管理
├── storage/              # 持久化层
│   ├── database.py       # SQLite 操作
│   └── models.py         # 数据模型
├── config.py             # 配置管理
├── main.py               # 入口
└── requirements.txt
```

## 数据源层

### 统一数据结构

```python
Article:
    title: str            # 标题
    url: str              # 原文链接
    source: str           # 来源名称
    published_at: datetime # 发布时间
    content: str          # 正文内容或摘要
    language: str         # 语言
```

### 数据源优先级

| 优先级 | 数据源 | 方式 | 说明 |
|--------|--------|------|------|
| 1 | RSS | feedparser | 免费、权威，主力来源。含 RSSHub 支持 |
| 2 | Reddit | JSON API（.json 后缀） | 免费，无需 API key。**风险提示**：Reddit 持续收紧非官方 API，此方式可能随时受限，架构上已通过统一接口预留切换成本 |
| 3 | 网页爬取 | httpx + BeautifulSoup | 兜底方案 |

### 预置中文数据源

- 机器之心 (jiqizhixin.com) — AI
- 36氪 (36kr.com) — 科技、创业
- 虎嗅 (huxiu.com) — 科技、商业
- 少数派 (sspai.com) — 科技、工具
- 爱范儿 (ifanr.com) — 消费科技
- 澎湃新闻 (thepaper.cn) — 时政、国际
- 通过 RSSHub：知乎热榜、微博热搜、新华网、央视新闻等

### 采集流程

1. 根据 topic 关键词，从已配置的数据源并行抓取（最大并发 5，单源超时 15 秒）
2. 按 `published_at` 排序，URL 去重
3. 返回最近 N 篇（默认 20 篇）交给预处理

### Topic 匹配逻辑

用户输入为自然语言（如"AI 最新资讯"），需要映射到已配置的 topic 标签：

1. **关键词匹配**：提取用户输入中的关键词，与数据源配置的 `topics` 字段做模糊匹配
2. **LLM 辅助分类**：当关键词匹配无结果时，用 LLM 从用户输入中提取 topic 意图，匹配最接近的已配置 topic
3. **未配置 topic 的处理**：如果用户查询的 topic 完全不在已配置范围内，告知用户当前支持的 topic 列表，并建议通过 `/addrss` 添加相关数据源

## 文章预处理（智能提取）

替代简单截断，分级提取文章关键内容：

### 分级策略

```
第一级：元数据摘要
  → RSS <description>/<summary>、HTML meta description、og:description
  → 如果内容 > 100 字，直接使用

第二级：结构化提取
  → 标题 + 副标题 + 前 2 段（倒金字塔核心信息）
  → 文章中的小标题/加粗文字（关键论点）
  → 末段（总结）

第三级：LLM 单篇摘要
  → 全文过长且前两级不足时，用便宜模型（如 Haiku）做单篇摘要
  → 缓存摘要到 SQLite，同一篇文章不重复处理
```

## LLM 层

### 统一接口

```python
summarize(articles: list[Article], topic: str) -> str
    # 输入一批文章，输出结构化摘要

chat(message: str, context: list[Message]) -> str
    # 带上下文的对话，用于追问深挖
```

### 双模型策略

- **轻量模型**（如 Haiku）：单篇文章摘要（第三级预处理）
- **强力模型**（如 Sonnet）：最终汇总分析、对话深挖

### 摘要输出格式

```
📋 【AI 最新资讯】2026-04-08

1. [标题] — 一句话摘要
   🔗 原文链接

2. [标题] — 一句话摘要
   🔗 原文链接

...

💡 综合分析：
整体趋势和关键洞察（2-3 句话）
```

## 对话与上下文管理

### 会话状态机

```
空闲状态 → 用户发送 topic 查询 → 进入会话状态
会话状态 → 用户追问 → 保持会话状态
会话状态 → 超时(10分钟) 或 新 topic → 结束当前会话，开启新会话
```

### 上下文存储

- 每个会话保存：topic、已获取的文章列表、对话历史
- 存入 SQLite，会话 ID 关联 Telegram chat_id
- 追问时，文章列表 + 历史对话一并发给 LLM

### 上下文长度控制

- 对话历史最多保留最近 10 轮
- 同时监控 token 数，超过阈值（如 4000 tokens）也触发压缩
- 压缩方式：用 LLM 对早期对话做压缩摘要，保留关键信息

## Telegram Bot 交互

### 命令列表

| 命令 | 说明 |
|------|------|
| `/start` | 欢迎信息 + 使用说明 |
| `/topic <关键词>` | 查询某个 topic 的最新资讯 |
| `/sources` | 查看已配置的数据源列表 |
| `/addrss <url>` | 添加自定义 RSS 源 |
| `/removerss <url>` | 移除 RSS 源 |
| `/model` | 查看/切换当前 LLM 后端 |
| `/help` | 帮助信息 |

### 自然语言支持

- 直接发送"AI 最新资讯"或"最近国际局势"也能识别为 topic 查询
- 会话状态下，任意消息视为追问

### 响应体验

- 先发"正在为你搜集资讯..."提示，同时发送 `ChatAction.TYPING` 持续显示输入状态
- 使用 Telegram HTML 格式化（避免 MarkdownV2 复杂的转义规则）
- 每条资讯附原文链接
- **消息长度处理**：Telegram 单条消息上限 4096 字符。摘要分为概览（Top 5 条 + 综合分析）和完整列表两部分，概览先发，用户点击"查看更多"后发送剩余条目

### 权限控制

- 配置文件中设置 Telegram user_id 白名单
- 白名单外用户发送消息时，回复"抱歉，您没有使用权限"并忽略后续消息
- 防止陌生人滥用 API 额度

## 配置管理

统一使用 `config.yaml` + 环境变量。**敏感信息（API key、bot token）默认从环境变量读取**，yaml 中只放非敏感配置：

```yaml
telegram:
  # bot_token 从环境变量 TELEGRAM_BOT_TOKEN 读取
  allowed_users: [123456789]

llm:
  provider: "claude"
  # api_key 从环境变量 LLM_API_KEY 读取
  summary_model: "claude-haiku-4-5-20251001"
  analysis_model: "claude-sonnet-4-6"

sources:
  rss:
    - name: "机器之心"
      url: "https://www.jiqizhixin.com/rss"
      topics: ["ai"]
    - name: "36氪"
      url: "https://36kr.com/feed"
      topics: ["tech", "ai"]
    - name: "知乎热榜"
      url: "https://rsshub.app/zhihu/hot"
      topics: ["general"]
  reddit:
    - subreddit: "artificial"
      topics: ["ai"]

cache_ttl: 3600
max_articles: 20
session_timeout: 600
```

仓库保留 `config.example.yaml`，实际配置文件加入 `.gitignore`。

## 持久化（SQLite）

### 存储内容

- **Topic 配置**：用户自定义的 RSS 源和 topic 映射
- **对话会话**：会话 ID、chat_id、topic、对话历史、关联文章
- **资讯缓存**：已抓取文章及其摘要，带 TTL 过期机制

## 错误处理策略

### 数据源层

- **单源失败**：记录错误日志，跳过该源，继续其他源的采集
- **全源失败**：回复用户"数据源暂时不可用，请稍后再试"，附带失败原因概要
- **单源超时**：15 秒超时，超时视为失败，走单源失败逻辑

### LLM 层

- **API 调用失败**：重试 1 次（间隔 2 秒），仍失败则尝试降级到备用模型
- **降级策略**：analysis_model 失败 → 用 summary_model 替代；summary_model 也失败 → 直接返回原始文章列表（跳过 LLM 摘要）
- **Rate limit**：捕获 429 错误，回复用户"请求过于频繁，请稍后再试"

### Bot 层

- 所有未捕获异常兜底处理，回复用户"处理出错，请重试"，避免 Bot 静默无响应

## 日志策略

使用 Python 标准 `logging` 模块：

- **INFO**：采集成功/失败、LLM 调用结果、用户命令
- **WARNING**：单源超时、rate limit、降级触发
- **ERROR**：全源失败、LLM 调用异常、未捕获异常
- **关键指标追踪**：LLM 调用耗时、token 用量、每次查询的数据源命中数

## 数据库 Schema（SQLite）

```sql
-- 用户自定义 RSS 源
CREATE TABLE custom_feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    topics TEXT NOT NULL,          -- JSON 数组，如 '["ai","tech"]'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话会话
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,           -- UUID
    chat_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    articles TEXT NOT NULL,        -- JSON 数组，关联的文章列表
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话历史
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,            -- 'user' 或 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 资讯缓存
CREATE TABLE article_cache (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT,                  -- 原始内容
    summary TEXT,                  -- LLM 生成的摘要（缓存）
    language TEXT,
    published_at TIMESTAMP,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 多语言处理

- 所有摘要和分析输出统一为**中文**
- 英文源（如 Reddit、英文 RSS）的内容，在 LLM 摘要阶段翻译为中文
- LLM prompt 中明确要求"请用中文输出"

## 技术栈

| 用途 | 技术 |
|------|------|
| Telegram Bot | python-telegram-bot |
| RSS 解析 | feedparser |
| HTTP 请求 | httpx |
| 网页解析 | beautifulsoup4 |
| LLM (Claude) | anthropic SDK |
| LLM (OpenAI) | openai SDK |
| 数据库 | sqlite3 (标准库) |
| 配置 | PyYAML |
| 异步 | asyncio (标准库) |

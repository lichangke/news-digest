# Daily News Digest

本项目用于按固定时段自动采集新闻、去重、生成日报、写入飞书知识库，并自动推送文档链接。

## 当前能力

- 支持双通道：
  - `general`：综合热点
  - `ai`：AI / 大模型资讯
- 支持 SQLite 状态库去重
- 支持联调专用 `--ignore-state`
- 支持分阶段 `.debug.md` 调试日志
- 支持飞书知识库自动创建年 / 月 / 日报节点并写入正文
- 支持自动推送日报链接到飞书会话
- 支持 cron 定时执行
- 支持重复跑时自动创建 `（重跑 HHMMSS）` 版本，避免覆盖旧文档

## 时间窗设计

当前采用两段制，覆盖完整 24 小时：

- `morning`：前一天 `17:00` → 当天 `08:00`
- `evening`：当天 `08:00` → 当天 `17:00`

默认 cron：

- `08:00` 运行 morning
- `17:00` 运行 evening

## 抓取策略

### general

`general` 已正式放弃中文 RSS 作为主线，当前主策略是：

1. 中文权威媒体栏目页 / 列表页抽取
2. 详情页二次抓取标题、摘要、发布时间
3. 搜索引擎补漏

当前重点中文源：

- 央视（CCTV）
- 界面（Jiemian）

质量控制包括：

- 来源优先级
- 事件级去重
- Jiemian 栏目黑名单强拦
- 更窄题材白名单

### ai

`ai` 通道继续使用 RSS / Atom 作为主线，适合 AI / 大模型 / 科技资讯场景。

## 目录结构

- `app/` 核心代码
- `config/` 配置文件
- `scripts/` 运行与部署脚本
- `logs/` 运行日志与 markdown 输出
- `state/` SQLite 状态库
- `PROJECT_LESSONS.md` 项目经验总结
- `PIPELINE_HARDENING_2026-03-14.md` 本次日报推送链路治理总结
- `docs/PIPELINE_MAINTAINER_QUICKSTART.md` 面向未来维护者的 1 分钟速读版

## 关键脚本

- `scripts/setup_venv.sh`：初始化虚拟环境
- `scripts/run_morning.sh`：运行 morning 双通道；内部拆分为生成结果 → 同步知识库 → 独立通知
- `scripts/run_evening.sh`：运行 evening 双通道；内部拆分为生成结果 → 同步知识库 → 独立通知
- `scripts/install_cron.sh`：安装 `08:00 / 17:00` 定时任务
- `scripts/feishu_doc_bridge.py`：本地桥接飞书开放平台 API，实现知识库节点自动确保与正文写入
- `scripts/send_news_notify.py`：读取单次运行结果 JSON 并发送通知
- `scripts/retry_notify.sh`：对已有结果文件执行一次补发通知
- `app/pipeline.py`：结构化流水线入口，产出 `runs/*.json`

## 手动运行

### 标准入口（推荐）

项目当前的**唯一标准主流程入口**是：

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general
```

### 联调 general

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general --ignore-state --no-sync-wiki
```

### 手动跑并同步飞书

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general
.venv/bin/python -m app.pipeline --run-type evening --channel ai
```

### 兼容入口（legacy）

`app.main` 仍可运行，但现在只作为兼容壳层，内部会委托给 `app.pipeline`。后续新增能力应只接入 `app.pipeline`。

### 安装 cron

```bash
bash scripts/install_cron.sh
```

## 配置要求

项目依赖工作区 `.env` 中的飞书与搜索配置，例如：

```env
TAVILY_API_KEY=...
FEISHU_APP_ID=...
FEISHU_APP_SECRET=...
```

同时需要在 `config/config.json` 中配置：

- `timezone`
- `channels.general`
- `channels.ai`
- `feishu.owner_open_id`
- `feishu.wiki_space_id`
- `feishu.wiki_root_node_token`

## 日志与排障

运行后会生成：

- `logs/*.md`：本次输出的日报 markdown
- `logs/*.debug.md`：抓取/去重后的调试日志
- `logs/morning.log` / `logs/evening.log`：shell 层运行与通知日志
- `runs/*.json`：单次运行的结构化结果文件

`runs/*.json` 是新的主排障入口，至少包含：

- 时间窗与开始/结束时间
- `counts`（抓取、去重、已存在、最终输出）
- markdown/debug 产物路径
- `wiki_plan`
- `stages.collect`
- `stages.wiki_sync`
- `stages.notify`

如果出现“日报生成了但没推送”，优先看对应 `runs/*.json`：

- `stages.wiki_sync.ok=true` 且 `stages.notify.ok=false`：说明可直接补发通知
- 补发方式：

```bash
bash scripts/retry_notify.sh runs/<result>.json
```

这样无需整条 morning / evening 任务重跑。

## 当前状态

项目主链路已经打通：

- 抓取 → 去重 → 飞书知识库落库 → 自动推送 → 定时执行

后续优化重点建议放在：

- `general` 中文源质量继续精修
- 推送 / 同步结果日志可观测性补强
- 知识库首页与目录呈现优化

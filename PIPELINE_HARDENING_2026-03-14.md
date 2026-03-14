# 每日新闻链路治理总结（2026-03-14）

本文档记录本次围绕“每日新闻没有推送”问题所做的排查、修复、结构化改造与最终结果，便于后续维护、复盘与交接。

## 1. 问题背景

用户反馈：**今天的每日新闻没有推送**。

排查后确认，当天 morning 任务并非未执行，而是出现了两类问题叠加：

1. **日报已成功生成并写入飞书知识库，但提醒消息没有成功送达**
2. **morning 文档标题日期取的是时间窗起始日（前一日 17:00），导致今天早上的文档显示成昨天日期**

这两个问题叠在一起，造成了“今天没有推送”的强烈表象。

---

## 2. 初步排查结论

通过查看 `crontab`、`logs/morning.log`、产出的 markdown/debug 文件以及飞书文档链接，确认：

- `0 8 * * * /root/.openclaw/workspace/news-digest/scripts/run_morning.sh` 已正确安装
- 2026-03-14 08:00 的 morning 定时任务确实执行成功
- 综合热点与 AI / 大模型两个通道都已完成知识库写入
- Feishu 发送能力本身可用，手动测试消息可以成功送达
- 问题主要集中在：
  - 脚本内消息发送调用结果被静默吞掉
  - morning 标题日期逻辑不符合用户感知

---

## 3. 本次修复与改造内容

### 3.1 修复 morning 文档日期逻辑

原先 wiki 标题与归档目录使用的是时间窗起点日期：

- morning：前一天 17:00 → 当天 08:00
- 标题却显示为“前一天日期”

现已修复为：

- wiki 标题与归档目录按**时间窗结束日**生成
- 因此 morning 文档会显示为“当天日期”

例如：

- 旧逻辑：`【2026年03月13日】早间新闻汇总`
- 新逻辑：`【2026年03月14日】早间新闻汇总`

---

### 3.2 消息发送不再静默失败

原先 `run_morning.sh` / `run_evening.sh` 中对：

```bash
openclaw message send ... >/dev/null 2>&1 || true
```

采用了彻底吞掉输出的方式，导致：

- 发送成功看不到凭据
- 发送失败没有日志
- 超时/阻塞也难定位

现已改为：

- 记录消息发送开始、结束、结果
- 失败时保留 exit code 和输出
- 不再依赖“静默 + 忽略错误”的方式掩盖问题

---

### 3.3 引入超时控制，避免长时间挂死

为了避免“某一步阻塞拖死整条链路”，新增了明确的超时边界：

- Python 主流程：`120s`
- Feishu 文档桥接：`90s`
- Feishu 通知发送：`25s`

这使得链路从“可能长时间不返回”变成：

- 成功完成
- 或明确超时退出，并留下可定位信息

---

### 3.4 增加分阶段日志与结构化运行结果

在原有 `logs/*.md` 与 `logs/*.debug.md` 基础上，新增：

- `logs/morning.log`
- `logs/evening.log`
- `runs/*.json`

其中 `runs/*.json` 成为新的主排障入口，记录：

- 运行时间窗
- 开始/结束时间
- 抓取/去重/已存在/最终输出数量
- markdown/debug 文件路径
- wiki 同步结果
- notify 结果

这样以后再遇到“日报生成了但没推送”，可以直接判断：

- `stages.wiki_sync.ok=true` 且 `stages.notify.ok=false`
- 说明日报主产物已成功，只需补发通知，无需整条重跑

---

### 3.5 将单段长脚本改造成可观测流水线

此前链路更接近“一段串行长脚本”，现在改造成了更清晰的小流水线：

1. **生成结果**：`app/pipeline.py`
2. **同步知识库**：在 pipeline 内执行并写入结果 JSON
3. **独立通知**：`scripts/send_news_notify.py`
4. **补发通知**：`scripts/retry_notify.sh <runs/result.json>`

这样带来的好处：

- 通知失败不再影响日报生成与知识库落库
- 出现异常时更容易知道失败点
- 可以按结果文件对某一次运行做局部补救

---

### 3.6 增加运维便利脚本

新增：

- `scripts/latest_run.sh <morning|evening> <general|ai>`

作用：

- 快速获取最近一次某通道某时段的结果文件路径
- 方便排障和补发通知

例如：

```bash
bash scripts/latest_run.sh morning general
bash scripts/latest_run.sh evening ai
```

---

### 3.7 修正 AI 通道标题后缀逻辑

在治理后期又发现一个遗留问题：

- AI 通道 morning 运行时，wiki 标题仍可能显示成“晚间汇总”

原因是配置中写死了：

- `wiki_title_suffix = "AI / 大模型晚间汇总"`

现已改为动态生成：

- morning → `AI / 大模型早间汇总`
- evening → `AI / 大模型晚间汇总`

避免继续误导阅读者。

---

### 3.8 清理运行产物的版本控制污染

本次为了验证新流水线，曾有两份 `runs/*.json` 被误提交进 git。

现已处理：

- `runs/*.json` 已加入 `.gitignore`
- 已误提交的运行结果文件已从 git 跟踪中移除

这样后续仓库中只保留代码和文档，不保留临时运行产物。

---

## 4. 实跑验证结果

本次改造后，已执行真实 morning 实跑验证。

验证结果：

- `bash scripts/run_morning.sh` 能够正常退出
- 不再出现之前那种“前台长时间挂住、不返回”的表现
- `general` 与 `ai` 通道都成功完成：
  - `stages.collect.ok = true`
  - `stages.wiki_sync.ok = true`
  - `stages.notify.ok = true`
- 结果 JSON、日志与飞书消息三者可互相印证

说明本次链路治理已经从“脆弱可用”推进到“可观测、可重试、可补救”的状态。

---

## 5. 本次关键提交

本轮治理涉及的关键提交包括：

- `02f837a` — `Fix morning wiki date and log notify results`
- `c7db68e` — `Harden news pipeline with timeouts and stage logs`
- `612b8c0` — `Decouple news pipeline stages and add retry notify`
- `977fb8a` — `Add latest run helper for news pipeline ops`
- `5b9a5b3` — `Fix AI wiki titles and ignore run artifacts`

这些提交基本构成了本次“日报推送链路治理”的完整演进过程。

---

## 6. 当前状态评估

截至 2026-03-14，本项目中与“日报生成 → 知识库同步 → 推送提醒”相关的链路已经具备：

- 超时控制
- 分阶段日志
- 结构化结果文件
- 通知失败可补发
- 最近一次运行结果快速定位
- 标题日期与 AI 时段标题逻辑修正
- 运行产物不再污染 git

因此这条链路已经达到：

> **适合继续稳定生产使用**

虽然仍有可继续打磨的空间（例如未来可统一 `run_date` 语义、进一步完善结果摘要视图），但不再是当前阻塞项。

---

## 7. 后续建议

### 7.1 可继续优化但不阻塞的项

1. 统一 `run_date` 的语义
   - 目前结果 JSON 中的 `run_date` 仍沿用时间窗起点日期
   - 而 wiki 标题已改为时间窗结束日期
   - 后续可考虑统一成“面向用户的自然展示日期”

2. 增加结果摘要脚本
   - 对 `runs/*.json` 做一行摘要展示
   - 例如输出：collect / wiki / notify 是否成功、URL 是什么

3. 若后续通知策略更复杂，可再引入轻量队列
   - 当前已足够支撑单用户、单会话的日报补发场景

### 7.2 当前建议的运维入口

- 运行 morning：

```bash
bash scripts/run_morning.sh
```

- 运行 evening：

```bash
bash scripts/run_evening.sh
```

- 查看最近一次结果：

```bash
bash scripts/latest_run.sh morning general
bash scripts/latest_run.sh morning ai
```

- 补发通知：

```bash
bash scripts/retry_notify.sh runs/<result>.json
```

---

## 8. 结论

本次修改不是单点修 bug，而是对“日报推送链路”做了一次完整的工程化收口：

- 修正用户可感知的日期问题
- 移除静默失败
- 控制阻塞风险
- 提高可观测性
- 支持局部补救
- 整理了更清晰的运维入口

这意味着项目从“能跑”进一步进化成了“更稳、更容易维护、更适合长期使用”的状态。

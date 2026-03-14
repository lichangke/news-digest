# 日报推送链路：维护者速查 / 最小运维手册

如果你只想快速理解当前这套“每日新闻 → 飞书知识库 → 推送提醒”链路，并在出问题时知道该怎么查、怎么补、怎么重跑，看这一页就够了。

---

## 1. 当前链路结构

链路已经拆成三段，不再是一个脆弱长脚本：

1. **生成结果**：`app/pipeline.py`（唯一标准主流程入口）
2. **同步知识库**：在 pipeline 内执行
3. **发送通知**：`scripts/send_news_notify.py`

对应外部入口：

- `bash scripts/run_morning.sh`
- `bash scripts/run_evening.sh`

说明：
- `run_morning.sh` / `run_evening.sh` 都会按顺序运行两个通道：`general` → `ai`
- 每个通道都会先生成 `runs/*.json`，再根据该结果决定是否发送通知
- notify 结果会回写到对应的 `runs/*.json`

---

## 2. 标准运行方式

## 日常标准运行

```bash
bash scripts/run_morning.sh
bash scripts/run_evening.sh
```

这两个脚本会：
- 调用 `python -m app.pipeline`
- 生成 `runs/*.json`
- 调用 `scripts/send_news_notify.py`
- 将 notify 结果写回 `runs/*.json`
- 将执行过程写入 `logs/morning.log` / `logs/evening.log`

## 手动找最近一次运行结果

```bash
bash scripts/latest_run.sh morning general
bash scripts/latest_run.sh morning ai
bash scripts/latest_run.sh evening general
bash scripts/latest_run.sh evening ai
```

## 手动单通道运行（调试 / 联调）

```bash
.venv/bin/python -m app.pipeline --run-type morning --channel general
.venv/bin/python -m app.pipeline --run-type evening --channel ai
```

常用附加参数：

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general --ignore-state
.venv/bin/python -m app.pipeline --run-type evening --channel general --no-sync-wiki
.venv/bin/python -m app.pipeline --run-type evening --channel general --demo
```

含义：
- `--ignore-state`：联调时忽略去重状态
- `--no-sync-wiki`：不写入知识库
- `--demo`：使用 demo 数据验证流程

---

## 3. 时间窗规则

当前采用固定双时段设计：

- `morning`：**前一日 17:00 → 当日 08:00**
- `evening`：**当日 08:00 → 当日 17:00**

这意味着：
- morning 文档标题按**时间窗结束日**显示
- 所以今天早上产出的文档，显示的是**今天日期**，这属于正常行为

如果有人觉得“日期不对”，先回到这里确认时间窗，而不是先怀疑标题逻辑。

---

## 4. 出问题先看哪里

### 第一优先：看结果文件

每次运行都会生成：

- `runs/*.json`

里面会记录：
- 抓取是否成功
- wiki 是否成功
- notify 是否成功
- markdown / debug 文件路径
- 最终文档 URL
- notify 相关状态

### 第二优先：看 debug 文件

- `logs/*.debug.md`

用于看候选数、去重结果、最终输出条目等阶段信息。

### 第三优先：看 shell / cron 日志

- `logs/morning.log`
- `logs/evening.log`

用于判断脚本层执行是否异常、是否超时、notify 回写是否完成。

### 最后再看 SQLite state

- `state/news.db`

说明：
- SQLite 当前主要用于文章去重状态
- `runs/*.json` 才是单次运行事实记录主来源
- 不要把 SQLite 当作主运行记录入口

---

## 5. 重跑与补发原则

### 原则 1：日报生成成功但通知失败，不要重跑整条任务

如果 `runs/*.json` 里看到：

- `stages.wiki_sync.ok=true`
- `stages.notify.ok=false`

说明：
- 知识库文档已经成功生成
- 失败只发生在通知阶段

这时**不要重跑整条日报**，直接补发：

```bash
bash scripts/retry_notify.sh runs/<result>.json
```

---

### 原则 2：先补发，后重跑

优先顺序应是：

1. 先确认 `runs/*.json` 是否已经存在
2. 如果 wiki 已成功，只补发 notify
3. 只有在主链路产物本身没生成、或 wiki 失败导致主结果不完整时，才考虑重跑

---

### 原则 3：重跑不应优先用于修通知问题

通知问题通常是局部问题。
如果文档已经在知识库里，就不该为了发一条提醒重做整条抓取与发布链路。

---

### 原则 4：SQLite state 可能影响重跑结果

如果你直接重跑某个时间窗：
- 已保存到 state 的文章可能被视为已处理
- 因此联调或重跑排查时，必要时应考虑：

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general --ignore-state
```

---

## 6. 最常见故障的判断方式

### 情况 1：日报生成了，但没收到提醒

看对应 `runs/*.json`：

- `stages.wiki_sync.ok=true`
- `stages.notify.ok=false`

处理方式：

```bash
bash scripts/retry_notify.sh runs/<result>.json
```

结论：
- 不要重跑整条任务
- 先补发通知

---

### 情况 2：任务卡住很久

当前链路已有超时保护：

- 主流程：120s
- wiki 桥接：90s
- notify：25s

正常情况下不会无限挂死。

优先检查：
- `logs/morning.log` / `logs/evening.log`
- 对应 `runs/*.json`
- 是否停在 pipeline、wiki 还是 notify 阶段

---

### 情况 3：标题日期看起来不对

先检查时间窗规则：
- morning 标题按时间窗结束日显示
- 这不是 bug，通常是时间窗理解偏差

AI 标题当前为动态生成：
- `AI / 大模型早间汇总`
- `AI / 大模型晚间汇总`

---

### 情况 4：`runs/*.json` 没生成

优先判断：
- `app.pipeline` 是否根本没跑起来
- shell 日志里是否已经报错
- `.venv/bin/python`、配置、依赖环境是否异常

先看：
- `logs/morning.log` / `logs/evening.log`

如果连 `result_path` 都没有，说明故障发生在结果文件落盘之前。

---

### 情况 5：`wiki_sync.ok=false`

说明主链路在知识库发布阶段失败。

此时优先做的不是立刻补发 notify，而是先确认：
- markdown 是否已生成
- debug 是否已生成
- wiki 失败是权限、结构、网络还是桥接脚本问题

先看：
- 对应 `runs/*.json`
- 其中 `stages.wiki_sync`
- 对应 `.debug.md`

---

### 情况 6：`notify_payload_missing`

这通常意味着：
- wiki URL 没拿到
- 或发布阶段未成功形成可通知 payload

这不是单纯“消息发送失败”，而是上游条件未满足。

处理时应先回看：
- `stages.wiki_sync`
- `notify_payload`

不要直接把它当成普通通知失败处理。

---

### 情况 7：某个 channel 没有产出结果

先判断是：
- 候选为空
- 被去重 / state 过滤掉了
- 还是抓取本身失败

先看：
- `runs/*.json` 里的 `counts`
- `logs/*.debug.md` 里的候选数、去重数、最终输出数

必要时可用：

```bash
.venv/bin/python -m app.pipeline --run-type evening --channel general --ignore-state
```

来排除 state 去重干扰。

---

## 7. 当前已知设计结论

1. 中文 `general` 不再把 RSS 当生产主线
2. 日报链路必须可观测，不能静默失败
3. 通知失败不能拖累日报主产物
4. `runs/*.json` 是主运行事实记录入口
5. SQLite state 主要用于去重，不是主运行事实来源
6. 运行产物不应进入 git（`runs/*.json` 已忽略）

---

## 8. 真正需要记住的命令

```bash
bash scripts/run_morning.sh
bash scripts/run_evening.sh
bash scripts/latest_run.sh morning general
bash scripts/latest_run.sh evening ai
bash scripts/retry_notify.sh runs/<result>.json
.venv/bin/python -m app.pipeline --run-type evening --channel general --ignore-state
```

---

## 9. 如果你要深入了解

建议继续看这三份：

- `README.md`
- `ARCHITECTURE_STATUS_2026-03-14.md`
- `PROJECT_FINALIZATION_TODO.md`

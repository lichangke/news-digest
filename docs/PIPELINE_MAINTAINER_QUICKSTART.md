# 日报推送链路：维护者 1 分钟速读

如果你只想快速理解当前这套“每日新闻 → 飞书知识库 → 推送提醒”链路，看这一页就够了。

## 现在的链路结构

链路已经拆成三段，不再是一个脆弱长脚本：

1. **生成结果**：`app/pipeline.py`（唯一标准主流程入口）
2. **同步知识库**：在 pipeline 内执行
3. **发送通知**：`scripts/send_news_notify.py`

对应外部入口：

- `bash scripts/run_morning.sh`
- `bash scripts/run_evening.sh`

---

## 出问题先看哪里

### 第一优先：看结果文件

每次运行都会生成：

- `runs/*.json`

里面会记录：

- 抓取是否成功
- wiki 是否成功
- notify 是否成功
- markdown / debug 文件路径
- 最终文档 URL

快速找最近一次结果：

```bash
bash scripts/latest_run.sh morning general
bash scripts/latest_run.sh morning ai
```

---

## 最常见故障的判断方式

### 情况 1：日报生成了，但没收到提醒

看对应 `runs/*.json`：

- `stages.wiki_sync.ok=true`
- `stages.notify.ok=false`

这说明知识库已经成功，只是通知没发出去。

**不要重跑整条任务**，直接补发：

```bash
bash scripts/retry_notify.sh runs/<result>.json
```

---

### 情况 2：任务卡住很久

当前链路已经有超时保护：

- 主流程：120s
- wiki 桥接：90s
- notify：25s

所以正常情况下不会无限挂死。

如果仍感觉异常，优先看：

- `logs/morning.log`
- `logs/evening.log`
- 对应的 `runs/*.json`

---

### 情况 3：标题日期看起来不对

当前规则：

- morning 知识库标题按**时间窗结束日**显示
- 所以今天早上产出的文档会显示为**今天日期**

AI 标题也已修复为动态生成：

- `AI / 大模型早间汇总`
- `AI / 大模型晚间汇总`

---

## 当前已知设计结论

1. 中文 `general` 不再把 RSS 当生产主线
2. 日报链路必须可观测，不能静默失败
3. 通知失败不能拖累日报主产物
4. 运行产物不应进入 git（`runs/*.json` 已忽略）

---

## 真正需要记住的 4 个命令

```bash
bash scripts/run_morning.sh
bash scripts/run_evening.sh
bash scripts/latest_run.sh morning general
bash scripts/retry_notify.sh runs/<result>.json
```

---

## 如果你要深入了解

建议继续看这三份：

- `README.md`
- `ARCHITECTURE_STATUS_2026-03-14.md`
- `PROJECT_FINALIZATION_TODO.md`

# news-digest 当前代码架构现状说明（2026-03-14）

> 这份文档用于说明：经过一轮“结构收束”之后，`news-digest` 当前代码架构已经演进到什么状态、完成了哪些重构、还存在哪些未完成项。

---

## 一、这轮重构的目标

本轮不是功能开发，而是“结构收束”。目标是把项目从：

- 能跑
- 但边界模糊

推进到：

- 主流程统一
- 通道边界清晰
- 采集 / 发布 / 质量规则开始分层
- 后续可以继续稳定演化

---

## 二、当前架构现状

目前项目已经形成以下几层：

### 1. 主流程层
- `app/pipeline.py`

职责：
- 读取配置
- 计算时间窗
- 编排候选采集
- 应用通道级质量策略
- 去重与 state 过滤
- 渲染 markdown / debug
- 编排 wiki 发布与 notify payload
- 产出 `runs/*.json`

当前结论：
- **已成为唯一标准主流程入口**

### 2. 兼容入口层
- `app/main.py`

职责：
- legacy 兼容壳层
- 内部委托给 `app.pipeline`

当前结论：
- **不再承担独立主流程职责**

### 3. 通道层
- `app/channels.py`
- `app/channel_policies.py`

职责：
- 定义 `general` / `ai` 通道策略
- 定义通道级质量策略对象
- 组织“候选收集 + 通道质量处理”

当前结论：
- **通道已从隐式配置分支升级为显式结构边界**

### 4. 数据源层
- `app/source_china.py`
- `app/source_rss_search.py`
- `app/source_common.py`

职责：
- 各类新闻源抓取与解析
- 标准化为 `NewsItem`

当前结论：
- **已从原先的 `fetchers.py` 超级文件中拆出主要 source 逻辑**

### 5. 抓取聚合层
- `app/fetchers.py`

职责：
- 作为较薄的候选抓取聚合入口
- 调用 channel strategy / source 层
- 提供 demo 数据

当前结论：
- **已明显瘦身，不再承担主要 source 实现细节**

### 6. 质量规则层
- `app/quality_rules.py`
- `app/general_quality.py`

职责：
- 存放 source-specific 规则（如 Jiemian / CCTV）
- 存放通用 quality 判定与 general 优先级逻辑

当前结论：
- **质量规则已开始脱离 source 代码，进入可独立维护层**

### 7. 发布层
- `app/publishers.py`
- `app/wiki_sync.py`
- `scripts/send_news_notify.py`

职责：
- wiki 发布
- notify payload 构造
- notify 发送与结果回写

当前结论：
- **发布层已开始显式化，但 notify 真正发送仍在脚本层**

### 8. 状态与可观测性层
- `app/storage.py`
- `runs/*.json`
- `logs/*.debug.md`
- shell logs

职责：
- SQLite 去重状态
- 单次运行结果记录
- 调试日志
- 脚本执行日志

当前结论：
- **可观测性结构已比较成熟，但 state/run 职责仍可继续收束**

---

## 三、这一轮已经完成的关键重构

按提交顺序看，已完成：

1. `82c387e` — 统一 `pipeline.py` 为标准入口
2. `9fdbf00` — 拆 source adapters，瘦身 `fetchers.py`
3. `fe05447` — 建立 explicit channel strategies
4. `bd81d32` — 引入 publisher helpers
5. `5ce47d6` — 抽离 source-specific quality rules
6. `352c1ea` — 增加 channel quality policies

这些变化叠加后的结果是：

> 项目骨架已经从“脚本式组织”明显转向“分层式组织”。

---

## 四、当前最清晰的主流程

现在的主流程已经可以概括为：

`pipeline`
→ `channel strategy`
→ `channel policy`
→ `source adapters`
→ `quality rules`
→ `dedupe`
→ `publishers`
→ `runs/*.json`

这个顺序已经比早期版本清楚很多。

---

## 五、当前仍未完全收束的点

虽然这一轮成果很实在，但还没有完全结束。

### 1. source-specific 规则仍有残留
虽然已经抽了一部分，但仍不是“完全干净的 source / quality 分离”。

### 2. notify 发送仍偏脚本层
`publishers.py` 已经承担了部分发布职责，但真正发送消息的动作还在 `scripts/send_news_notify.py`。

### 3. state 与 run model 还没完全统一
目前：
- SQLite 主要负责去重
- `runs/*.json` 是运行真相源

这个分工已经比较明确，但还没有在代码与文档层做最终收束定义。

### 4. 目录结构仍是过渡态
虽然已经分层，但还没有完全演化成更清晰的子目录化结构（如 `sources/`, `filters/`, `publishers/` 子包）。

---

## 六、当前可认为“已经稳定”的部分

下面这些在当前阶段可以视为较稳定骨架：

- `pipeline.py` 作为唯一标准入口
- `runs/*.json` 作为主排障入口
- `general` / `ai` 双通道结构
- source 层拆分方向
- publisher helper 方向
- quality rules 独立成层

这些方向不建议再反复摇摆。

---

## 七、对维护者的实际建议

如果你是未来维护者，当前应该这样理解这个项目：

### 不要再把新逻辑直接塞回 `pipeline.py`
主流程应该保持编排层定位。

### 不要把质量规则重新塞回 source 函数
新规则优先进 `quality_rules.py` / `general_quality.py` / `channel_policies.py`。

### 不要重新制造新的平行入口
标准入口就是 `app.pipeline`。

### 遇到运行问题，先看 `runs/*.json`
这是当前运行事实的主入口。

---

## 八、一句话总结

> 截至 2026-03-14，这一轮重构已经把 `news-digest` 从“高质量原型系统”推进到了“具备清晰分层骨架的可维护系统”，但仍处于收束中的中后段，而不是最终完成态。

接下来若继续推进，重点应放在：

- 继续清理剩余规则耦合
- 明确 state / run model 边界
- 再决定是否继续子包化目录结构

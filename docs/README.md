# news-digest docs

本目录用于存放 `news-digest` 项目的架构、维护、运行与后续收尾文档。

如果你是第一次接手这个项目，建议按下面顺序阅读。

---

## 建议阅读顺序

### 1. `PIPELINE_MAINTAINER_QUICKSTART.md`
**适合场景：**
- 只想快速理解当前日报推送链路
- 需要立刻知道怎么跑、怎么查、怎么补发

**你会看到：**
- 当前主链路结构
- 最常见故障的判断方式
- 最常用命令
- 维护者最低限度需要知道的事实

---

### 2. `ARCHITECTURE_STATUS_2026-03-14.md`
**适合场景：**
- 想理解这一轮结构收束后，项目当前架构处于什么状态
- 想知道哪些重构已经完成，哪些还没完全收口

**你会看到：**
- 当前代码分层
- 本轮关键重构成果
- 已稳定的骨架
- 仍未完全收束的点

---

### 3. `PROJECT_FINALIZATION_TODO.md`
**适合场景：**
- 想知道这个项目接下来应该怎么收尾
- 需要一份按执行顺序整理好的落地清单

**你会看到：**
- 当前项目判断
- 收尾原则
- 分阶段 TODO
- 推荐执行顺序
- 最终验收标准

---

### 4. `TECHNICAL_ARCHITECTURE.md`
**适合场景：**
- 需要系统性理解项目的完整技术架构
- 做中长期维护、交接、复盘或二次演进

**你会看到：**
- 更完整的架构说明
- 模块与职责全景
- 设计与实现之间的关系

---

## 每份文档的定位

- `PIPELINE_MAINTAINER_QUICKSTART.md`
  - **定位：** 维护者速查页
  - **关注点：** 怎么跑、怎么查、怎么补

- `ARCHITECTURE_STATUS_2026-03-14.md`
  - **定位：** 当前架构现状说明
  - **关注点：** 现在代码被收束到了什么程度

- `PROJECT_FINALIZATION_TODO.md`
  - **定位：** 后续收尾与落地计划
  - **关注点：** 下一步该做什么

- `TECHNICAL_ARCHITECTURE.md`
  - **定位：** 完整技术架构文档
  - **关注点：** 全局理解与长期维护

---

## 维护建议

- 快速排障时，先看 quickstart，再看最近一次 `runs/*.json`
- 评估是否继续重构时，先看 architecture status 和 finalization todo
- 不要把新设计决策只留在聊天里；应尽量补到本目录文档中

---

## 一句话总结

如果只想最快接手：

> 先看 `PIPELINE_MAINTAINER_QUICKSTART.md`，再看 `ARCHITECTURE_STATUS_2026-03-14.md`，最后看 `PROJECT_FINALIZATION_TODO.md`。

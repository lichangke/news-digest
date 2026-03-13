# 每日新闻项目：双通道设计

## 目标

将“每日新闻项目”拆成两条并行通道：

1. **综合热点通道（general）**
   - 面向全网综合热点
   - 优先信源：央视、人民网、新华网、澎湃、界面等
   - 检索入口：Tavily + Multi-Search-Engine + 权威站点核验

2. **AI / 大模型通道（ai）**
   - 面向 AI、模型、科技与开发者社区动态
   - 主要入口：RSS / Atom 订阅源
   - 可由 blogwatcher 或项目脚本自行拉取

## 当前配置状态

- `config/config.json` 已加入 `channels.general` 与 `channels.ai`
- `config/blogwatcher-feeds.json` 已保存 AI 通道 RSS 源清单
- 若后续接入 blogwatcher，可直接使用这份 feeds 列表

## AI 通道 RSS 源

- 36kr
- 机器之心
- 量子位
- 智东西
- 雷峰网
- AIbase
- OpenAI Blog
- Anthropic
- MIT Technology Review
- TechCrunch AI
- Hacker News Best
- arXiv cs.AI
- GitHub Trending AI
- Reddit r/MachineLearning
- 微博热搜（RSSHub）
- 知乎话题（RSSHub）

## 设计原则

### 综合热点通道
- 适合你的主需求：早晚固定时段的综合新闻汇总
- 重点在权威性、完整度、去重与发布时间边界

### AI 通道
- 适合做垂直领域简报
- 更容易稳定获取结构化更新
- 需要额外做事件归并与信源分级，避免同一模型更新被多站重复转载

## 后续待完成

1. 将 Tavily 检索接入 general 通道脚本
2. 将 Multi-Search-Engine 接入 general 通道脚本
3. AI 通道继续沿用 RSS / Atom 订阅源
4. general 通道放弃 RSS 主线，改做中文权威媒体栏目页 / 列表页抽取 + 正文页二次抓取 + 搜索引擎兜底补漏
5. 为 AI 通道建立独立的去重与汇总策略
6. 决定 AI 通道是独立知识库分支还是并入每日汇总体系

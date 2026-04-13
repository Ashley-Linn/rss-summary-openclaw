---
name: rss-summary
description: 从本地 FreshRSS 获取最新文章，调用 DeepSeek 生成综合日报，并通过飞书企业机器人发送单聊消息
tools:
  - python
  - http_request
---

# RSS 新闻摘要技能

## 触发条件
- 用户说：“发送新闻摘要”、“给我今天的新闻”、“每日新闻”、“今日有什么新闻”、“今日新闻有没有什么值得关注的”
- 或者通过定时任务（例如每天 8:30）自动触发

# 执行规则（使用包装脚本，确保环境一致）
- 执行命令：/home/ashley/.openclaw/skills/rss-summary/run.sh

## 执行流程
1. 执行包装脚本 `run.sh`，该脚本会：
   - 切换到技能目录
   - 使用虚拟环境的 Python 运行 `fetch_and_push.py`
2. 脚本自动完成：
   - 从 FreshRSS 聚合源（支持筛选模式/全量模式）获取最新文章，或直接从独立 URL 列表抓取
   - 将所有文章（标题、链接、摘要）一次性提交给 DeepSeek API
   - DeepSeek 生成一份**综合日报**，包含：
     * 按主题分类（如科技、医药、时政等）
     * 每条新闻一句话概括核心，并附原文链接
     * 今日重点总结（3-5点）
   - 将日报通过飞书 API 发送到指定用户单聊（如超长自动分批）
   - 将日报追加到 Obsidian 笔记 `Daily News/YYYY-MM-DD.md`
3. 返回执行结果（控制台输出和飞书消息）

## 环境变量（必须配置）
- `FRESHRSS_URL`: 带 token 的 FreshRSS 聚合源地址（示例：`http://localhost:8080/feeds/用户/token?hours=24`）
- `USE_FRESHRSS`: 是否使用 FreshRSS 聚合源（true/false），默认 true
- `FILTER_MODE`: 当 USE_FRESHRSS=true 时，是否只输出白名单中的源（true/false）
- `FOCUS_FEATURES_JSON`: JSON 数组，白名单关键词（如 `["chinanews.com.cn","MP_WXS_xxx"]`）
- `DIRECT_FEED_URLS_JSON`: 当 USE_FRESHRSS=false 时，直接抓取的 RSS 源列表（JSON 数组）
- `FEISHU_APP_ID`: 飞书企业自建应用的 App ID
- `FEISHU_APP_SECRET`: 飞书企业自建应用的 App Secret
- `FEISHU_USER_OPEN_ID`: 接收消息的用户 open_id（可从飞书后台或 API 获取）
- `DEEPSEEK_API_KEY`: DeepSeek API Key（用于生成摘要）
- `OBSIDIAN_VAULT_PATH`: Obsidian 仓库的本地路径（WSL 格式，例如 `/mnt/d/MyNotes/Obsidian`）
- `MAX_ARTICLES`: 最多获取的文章数量（默认 30）

## 权限要求
- 飞书应用需开通：`im:message`、`im:message:send_as_bot`
- 无需配置事件回调（脚本主动调用 API 发送）

## 注意事项
- 确保虚拟环境中已安装依赖：`feedparser`, `requests`, `python-dotenv`
- 必须使用技能独立虚拟环境运行，禁止使用系统 Python
- 环境变量必须在 `.env` 文件中配置完整，缺少任一关键变量脚本会报错
- 筛选模式依赖于 `FOCUS_FEATURES_JSON` 中的关键词，请根据实际 RSS 条目中的链接域名或 feed ID 调整
- 直接抓取模式（`USE_FRESHRSS=false`）需要配置 `DIRECT_FEED_URLS_JSON`
- **日报生成方式**：将所有文章一次性提交给 DeepSeek，生成综合日报；若 API 调用失败，则降级为简单列表
- 飞书单条消息长度限制约 2000 字符，超长时会自动拆分成多条消息发送（每条带分段标识）
- **脚本已内置超时和实时输出**：所有网络请求均有超时（30-60 秒），且每个步骤都会打印带刷新的日志，避免 OpenClaw 调用时因长时间无输出而认为脚本卡住
- **手动测试命令**：
  `/home/ashley/.openclaw/skills/rss-summary/.venv/bin/python /home/ashley/.openclaw/skills/rss-summary/fetch_and_push.py`
- 若定时任务不执行，查看网关日志：`openclaw logs --follow`
- Obsidian 写入路径必须可写，建议先用 `test_obsidian.py` 验证
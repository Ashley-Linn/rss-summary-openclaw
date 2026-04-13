#!/home/ashley/.openclaw/skills/rss_summary/.venv/bin/python
# 保存路径: ~/.openclaw/skills/rss_summary/fetch_and_push.py

# ============================
# 依赖库
import os
import sys
import time
import datetime
import json
import re
import socket
import feedparser
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
from pathlib import Path

# ========== 强制刷新输出缓冲区，避免 OpenClaw 认为卡死 ==========
sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+ 可用
# 或者每次 print 时加 flush=True，下面所有 print 都会加上 flush=True

print("脚本启动", flush=True)

# ========== 设置全局 socket 超时（备用） ==========
socket.setdefaulttimeout(30)

# 获取脚本所在目录的绝对路径
script_dir = Path(__file__).parent.absolute()
os.chdir(script_dir)
print(f"当前工作目录: {os.getcwd()}", flush=True)
load_dotenv(dotenv_path=script_dir / ".env")
print("环境变量加载完成", flush=True)

# ========== 读取环境变量 ==========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
YOUR_OPENID = os.getenv("FEISHU_USER_OPEN_ID")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "30"))

# ========== 模式选择 ==========
USE_FRESHRSS = os.getenv("USE_FRESHRSS", "true").lower() == "true"
if USE_FRESHRSS:
    FRESHRSS_URL = os.getenv("FRESHRSS_URL")
    if not FRESHRSS_URL:
        raise ValueError("USE_FRESHRSS=true 但未设置 FRESHRSS_URL")
    FILTER_MODE = os.getenv("FILTER_MODE", "true").lower() == "true"
else:
    FRESHRSS_URL = None
    FILTER_MODE = False

direct_feed_urls_json = os.getenv("DIRECT_FEED_URLS_JSON", "[]")
try:
    DIRECT_FEED_URLS = json.loads(direct_feed_urls_json)
except json.JSONDecodeError:
    print("错误: DIRECT_FEED_URLS_JSON 格式不正确，请使用 JSON 数组", flush=True)
    DIRECT_FEED_URLS = []

focus_features_json = os.getenv("FOCUS_FEATURES_JSON", "[]")
try:
    FOCUS_FEATURES = json.loads(focus_features_json)
except json.JSONDecodeError:
    print("错误: FOCUS_FEATURES_JSON 格式不正确，请使用 JSON 数组", flush=True)
    FOCUS_FEATURES = []

required_vars = ["DEEPSEEK_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_USER_OPEN_ID"]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"缺少环境变量: {var}")

if USE_FRESHRSS and not FRESHRSS_URL:
    raise ValueError("USE_FRESHRSS=true 但未设置 FRESHRSS_URL")
if not USE_FRESHRSS and not DIRECT_FEED_URLS:
    raise ValueError("USE_FRESHRSS=false 但 DIRECT_FEED_URLS_JSON 为空")

print("配置加载完成", flush=True)

# ============================
# 函数1：从 FreshRSS 获取文章列表（模式 A）
# ============================
def get_articles_via_freshrss():
    print("开始获取 FreshRSS 聚合源...", flush=True)
    try:
        resp = requests.get(FRESHRSS_URL, timeout=30)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"获取 FreshRSS 失败: {e}", flush=True)
        return []
    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        if not FILTER_MODE:
            articles.append({
                "title": entry.get("title", "无标题"),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", "")[:200]
            })
            continue

        link = entry.get("link", "")
        source_title = ""
        if hasattr(entry, 'feed') and hasattr(entry.feed, 'title'):
            source_title = entry.feed.title
        if not source_title and 'source' in entry:
            source_title = entry.source.get('title', '')
        combined = f"{link} {source_title}".lower()
        matched = any(feature.lower() in combined for feature in FOCUS_FEATURES)
        if matched:
            articles.append({
                "title": entry.get("title", "无标题"),
                "link": link,
                "summary": entry.get("summary", "")[:200]
            })
        else:
            print(f"跳过: {source_title} | {link[:80]}", flush=True)
    print(f"获取到 {len(articles)} 篇文章 (FreshRSS)", flush=True)
    return articles

# ============================
# 函数2：直接抓取独立 URL 列表（模式 B）
# ============================
def get_articles_direct():
    print("开始直接抓取独立 URL 列表...", flush=True)
    all_articles = []
    for feed_url in DIRECT_FEED_URLS:
        print(f"正在获取: {feed_url}", flush=True)
        try:
            # 使用 requests 获取内容，设置超时，避免 feedparser 无限等待
            resp = requests.get(feed_url, timeout=30)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                all_articles.append({
                    "title": entry.get("title", "无标题"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200]
                })
        except Exception as e:
            print(f"获取 {feed_url} 失败: {e}", flush=True)
    # 按链接去重
    seen = set()
    unique = []
    for art in all_articles:
        if art["link"] not in seen:
            seen.add(art["link"])
            unique.append(art)
    print(f"直接抓取获取到 {len(unique)} 篇文章", flush=True)
    return unique[:MAX_ARTICLES]

def get_articles():
    if USE_FRESHRSS:
        print("使用模式: FreshRSS 聚合源" + (" (筛选模式)" if FILTER_MODE else " (全量模式)"), flush=True)
        return get_articles_via_freshrss()
    else:
        print("使用模式: 独立 URL 列表", flush=True)
        return get_articles_direct()

# ============================
# 函数3：获取飞书 tenant_access_token
# ============================
def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取飞书token失败: {data}")
    return data["tenant_access_token"]

# ============================
# 函数4：发送纯文本消息到飞书单聊
# ============================
def send_message(text):
    try:
        token = get_feishu_token()
    except Exception as e:
        print(f"获取token失败: {e}", flush=True)
        return
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    content_json = json.dumps({"text": text})
    data = {
        "receive_id": YOUR_OPENID,
        "msg_type": "text",
        "content": content_json
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code != 200:
            print("飞书发送失败:", resp.text, flush=True)
        else:
            print("✅ 新闻已发送到飞书单聊", flush=True)
    except Exception as e:
        print(f"❌ 发送失败: {e}", flush=True)

# ============================
# 函数5：生成综合日报（一次性调用 DeepSeek，带重试机制）
# ============================
def generate_daily_report(articles):
    if not articles:
        return "今日无新文章。"

    # 第一步：清洗和精简摘要（每篇200字，去HTML）
    cleaned = []
    for art in articles:
        summary = art['summary'][:200]
        summary = re.sub(r'<[^>]+>', '', summary)   # 去HTML标签
        summary = ' '.join(summary.split())         # 合并空白
        cleaned.append({
            'title': art['title'],
            'link': art['link'],
            'summary': summary
        })

    # 第二步：动态限制总字符数不超过4000
    MAX_CHARS = 4000
    selected = []
    total_chars = 0
    for art in cleaned:
        item_chars = len(art['title']) + len(art['link']) + len(art['summary']) + 20
        if total_chars + item_chars <= MAX_CHARS:
            selected.append(art)
            total_chars += item_chars
        else:
            break
    if not selected:
        selected = [cleaned[0]]

    # 构建新闻列表文本
    news_text = ""
    for idx, art in enumerate(selected, 1):
        news_text += f"{idx}. 标题：{art['title']}\n   链接：{art['link']}\n   摘要：{art['summary']}\n\n"

    prompt = f"""你是一个专业的新闻编辑。请根据以下 {len(selected)} 条新闻，生成一份中文日报。要求：
1. 按主题分类（如科技、医药、时政、互联网等），每个类别下列出相关新闻。
2. 每条新闻用一句话概括核心，并附上原文链接。
3. 最后给出今日重点总结（3-5点）。
4. 语言简洁，总字数不超过1500字。

新闻列表：
{news_text}
"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个专业的新闻编辑，擅长整合信息并生成简洁日报。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.7
    }

    # 重试机制：仅针对超时重试2次
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            print(f"请求超时 (尝试 {attempt+1}/{max_retries+1})", flush=True)
            if attempt == max_retries:
                break
            time.sleep(2)
        except Exception as e:
            print(f"生成日报失败: {e}", flush=True)
            break
    else:
        # 所有重试均失败，降级
        fallback = "\n\n".join([f"{idx}. {art['title']}\n{art['link']}" for idx, art in enumerate(selected, 1)])
        return f"⚠️ AI 摘要服务暂时不可用，以下为原始新闻列表：\n\n{fallback}"

# ============================
# 函数6：发送日报到飞书（无多余确认消息）
# ============================
def send_to_feishu(report_text):
    if not report_text:
        report_text = "今日无新文章。"
    MAX_LEN = 1900
    if len(report_text) <= MAX_LEN:
        send_message(report_text)
    else:
        parts = []
        current = ""
        for line in report_text.split('\n'):
            if len(current) + len(line) + 1 > MAX_LEN:
                parts.append(current)
                current = line
            else:
                current += '\n' + line if current else line
        if current:
            parts.append(current)
        for idx, part in enumerate(parts, 1):
            header = f"📰 日报 {idx}/{len(parts)}\n\n" if len(parts) > 1 else "📰 今日新闻日报\n\n"
            send_message(header + part)
            time.sleep(0.5)

# ============================
# 函数7：保存日报到 Obsidian
# ============================
def save_to_obsidian(articles, report):
    if not OBSIDIAN_VAULT_PATH:
        print("未配置 OBSIDIAN_VAULT_PATH, 跳过写入 Obsidian", flush=True)
        return
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    note_dir = os.path.join(OBSIDIAN_VAULT_PATH, "Daily News")
    os.makedirs(note_dir, exist_ok=True)
    note_file = os.path.join(note_dir, f"{today}.md")
    with open(note_file, "a", encoding="utf-8") as f:
        f.write(f"\n## 📰 新闻日报 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(report)
        f.write("\n---\n")
    print(f"✅ 已写入 Obsidian: {note_file}", flush=True)

# ============================
# 主程序入口
# ============================
if __name__ == "__main__":
    try:
        print("开始获取今日新闻...", flush=True)
        articles = get_articles()
        print(f"成功获取 {len(articles)} 条新闻", flush=True)
        if articles:
            print("生成日报...", flush=True)
            report = generate_daily_report(articles)
            print("发送到飞书...", flush=True)
            send_to_feishu(report)
            print("保存到Obsidian...", flush=True)
            save_to_obsidian(articles, report)
            print("任务完成！", flush=True)
        else:
            print("今日无新闻", flush=True)
            send_to_feishu("今日无新闻可关注")
    except Exception as e:
        print(f"执行失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
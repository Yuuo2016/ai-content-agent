import re
import feedparser
import requests

# 内容运营相关的默认 RSS 源（可自行增删）
DEFAULT_RSS_FEEDS = [
    "https://36kr.com/feed",                     # 36氪（科技/商业）
    "https://www.jiqizhixin.com/rss",            # 机器之心（AI）
    "https://feeds.feedburner.com/TheHackerNews",# 黑客新闻（安全）
    "https://hnrss.org/frontpage",               # Hacker News
    "https://www.reddit.com/r/technology/.rss",  # Reddit 科技
    "https://www.reddit.com/r/artificial/.rss",  # Reddit AI
]

GITHUB_TRENDING_LANGS = ["python", "javascript", "typescript"]

# 热门话题榜 RSS 源（通过 RSSHub 公共实例）
# RSSHub 是开源项目，将各平台热榜转为标准 RSS
HOT_TOPICS_FEEDS = [
    "https://rsshub.app/zhihu/hotlist",          # 知乎热榜
    "https://rsshub.app/weibo/search/hot",        # 微博热搜
    "https://rsshub.app/baidu/topwords",          # 百度热搜
    "https://rsshub.app/36kr/hot-list",           # 36氪热榜
]

# 备用热门话题源（直接 API，无需 RSSHub）
BACKUP_HOT_APIS = [
    # V2EX 热门话题（官方 API）
    {"url": "https://www.v2ex.com/api/topics/hot.json", "type": "v2ex"},
    # Hacker News 热门（官方 API）
    {"url": "https://hacker-news.firebaseio.com/v0/topstories.json", "type": "hn"},
]


def _clean_html(text: str) -> str:
    """清洗 HTML 标签"""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_hot_topics(limit_per_feed: int = 10, timeout: int = 10) -> list:
    """加分项：自动发现热门话题。

    抓取知乎热榜、微博热搜、百度热搜等热门话题榜，
    让内容运营 Agent 能自动感知当前全网在讨论什么。

    优先用 RSSHub，失败时降级到备用 API。
    """
    items = []

    # 1. 尝试 RSSHub 热门话题源
    for url in HOT_TOPICS_FEEDS:
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            source_name = parsed.feed.get("title", url)
            for entry in parsed.entries[:limit_per_feed]:
                title = _clean_html(entry.get("title", "").strip())
                if title:
                    items.append({
                        "title": title,
                        "url": entry.get("link", ""),
                        "source": source_name,
                        "summary": _clean_html((entry.get("summary", "") or "")[:200]),
                        "type": "hot_topic",
                    })
        except Exception as e:
            print(f"  [提示] 热门话题源 {url} 不可用: {e}")

    # 2. 如果 RSSHub 全部失败，用备用 API
    if not items:
        print("  [提示] RSSHub 热门话题不可用，启用备用源...")
        items = _fetch_backup_hot()

    # 去重
    seen = set()
    result = []
    for it in items:
        key = it["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(it)
    return result[:30]


def _fetch_backup_hot() -> list:
    """备用热门话题源：V2Ex 热门 + Hacker News Top"""
    items = []

    # V2Ex 热门
    try:
        resp = requests.get(
            "https://www.v2ex.com/api/topics/hot.json",
            timeout=10, headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        for topic in resp.json()[:10]:
            items.append({
                "title": topic.get("title", ""),
                "url": topic.get("url", ""),
                "source": "V2EX 热门",
                "summary": _clean_html((topic.get("content", "") or "")[:200]),
                "type": "hot_topic",
            })
    except Exception as e:
        print(f"  [提示] V2Ex 热门不可用: {e}")

    # Hacker News Top 10
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10,
        )
        resp.raise_for_status()
        top_ids = resp.json()[:10]
        for story_id in top_ids:
            try:
                story = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=5,
                ).json()
                if story and story.get("title"):
                    items.append({
                        "title": story["title"],
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "source": "Hacker News Top",
                        "summary": f"评分: {story.get('score', 0)} | 评论: {story.get('descendants', 0)}",
                        "type": "hot_topic",
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"  [提示] Hacker News Top 不可用: {e}")

    return items


def fetch_rss(feeds=None, limit_per_feed: int = 5, timeout: int = 8) -> list:
    feeds = feeds or DEFAULT_RSS_FEEDS
    items = []
    for url in feeds:
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:limit_per_feed]:
                items.append({
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "source": parsed.feed.get("title", url),
                    "summary": (entry.get("summary", "") or "")[:300],
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[警告] RSS 抓取失败 {url}: {e}")
    return items


def fetch_github_trending(limit: int = 10) -> list:
    items = []
    headers = {"Accept": "application/vnd.github+json"}
    for lang in GITHUB_TRENDING_LANGS:
        try:
            url = (
                "https://api.github.com/search/repositories"
                f"?q=created:>{_days_ago(7)}+language:{lang}"
                "&sort=stars&order=desc&per_page=5"
            )
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            for repo in resp.json().get("items", [])[:limit]:
                items.append({
                    "title": f"[GitHub] {repo['full_name']}",
                    "url": repo["html_url"],
                    "source": "GitHub Trending",
                    "summary": (repo.get("description") or "")[:300],
                    "published": repo.get("created_at", ""),
                })
        except Exception as e:
            print(f"[警告] GitHub 抓取失败 {lang}: {e}")
    return items


def _days_ago(n: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def fetch_all(max_items: int = 20) -> list:
    items = fetch_rss() + fetch_github_trending()
    seen = set()
    result = []
    for it in items:
        key = it["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(it)
    return result[:max_items]

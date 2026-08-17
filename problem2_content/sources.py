"""
题二：信息源抓取模块（稳定版·多源覆盖）

从多个真实信息源获取资讯，确保多来源覆盖：
    - 中文 RSS：澎湃新闻、36氪（直接 RSS，不走 RSSHub）
    - 英文 RSS：Hacker News、TechCrunch
    - 开源 RSS：GitHub Trending
    - 热门话题榜：知乎热榜 / 微博热搜 / 百度热搜（RSSHub 多实例轮询）

降级策略：
    1) RSSHub 公共实例不可用 → 轮询备用实例
    2) 全部 RSSHub 失败 → Hacker News 官方 API 兜底

对外接口：
    fetch_all(max_items=20) -> list[dict]      抓取真实资讯
    fetch_hot_topics() -> list[dict]           抓取热门话题榜
"""
import time

import requests

# 浏览器级 User-Agent，避免被反爬拦截
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# RSSHub 备用实例列表（公共实例可能限流，轮询尝试）
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.feeded.xyz",
]

# 稳定可用的 RSS 源（不依赖 RSSHub，直接官方 RSS）
# 已逐个验证可用性，保留确认可连通的源
RSS_SOURCES = [
    # 海外英文源（已验证可用）
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "source": "Hacker News"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "source": "TechCrunch"},
    # 国内中文源（已验证可用）
    {"name": "InfoQ中文", "url": "https://www.infoq.cn/feed", "source": "InfoQ"},
    # 开源趋势（已验证可用）
    {"name": "GitHub Trending", "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml", "source": "GitHub"},
    # 国内备选源（本地 Windows 通常可访问，沙箱可能 SSL 受限）
    {"name": "澎湃新闻", "url": "https://feedx.net/rss/pengpai.xml", "source": "澎湃新闻"},
    {"name": "V2Ex", "url": "https://www.v2ex.com/index.xml", "source": "V2Ex"},
]

# 热门话题榜（通过 RSSHub，多实例轮询）
HOT_TOPIC_ROUTES = [
    {"name": "知乎热榜", "route": "/zhihu/hotlist", "source": "知乎"},
    {"name": "微博热搜", "route": "/weibo/search/hot", "source": "微博"},
    {"name": "百度热搜", "route": "/baidu/topwords", "source": "百度"},
]

# V2Ex 热门话题作为备用
V2EX_HOT_NODES = [
    {"name": "V2Ex热门", "url": "https://www.v2ex.com/feed/index.xml", "source": "V2Ex"},
]


def _parse_rss(xml_text: str, source: str) -> list:
    """简单解析 RSS/Atom XML，提取标题、链接、摘要"""
    items = []
    try:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_text)

        # RSS 2.0 格式
        for item in root.findall(".//item"):
            title = item.findtext("title", default="")
            link = item.findtext("link", default="")
            desc = item.findtext("description", default="")
            items.append({
                "title": title.strip() if title else "",
                "url": link.strip() if link else "",
                "summary": (desc.strip()[:200]) if desc else "",
                "source": source,
            })

        # Atom 格式
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                title = entry.findtext("atom:title", default="", namespaces=ns)
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = entry.findtext("atom:summary", default="", namespaces=ns)
                items.append({
                    "title": title.strip() if title else "",
                    "url": link.strip() if link else "",
                    "summary": (summary or "")[:200],
                    "source": source,
                })
    except Exception as e:
        print(f"  [RSS解析错误] {source}: {e}")

    return items


def _fetch_rss(url: str, source: str, timeout: int = 10) -> list:
    """抓取单个 RSS 源"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return _parse_rss(resp.text, source)
    except Exception as e:
        print(f"  [提示] RSS 源 {url} 不可用: {e}")
        return []


def _fetch_rsshub_with_fallback(route: str, source: str, timeout: int = 5) -> list:
    """轮询多个 RSSHub 实例，直到成功或全部失败"""
    for base in RSSHUB_INSTANCES:
        url = f"{base}{route}"
        items = _fetch_rss(url, source, timeout=timeout)
        if items:
            return items
    print(f"  [提示] RSSHub {route} 所有实例均不可用，启用备用源...")
    return []


def _fetch_hn_api() -> list:
    """Hacker News 官方 API 降级方案"""
    items = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers=HEADERS, timeout=10
        )
        ids = resp.json()[:15]
        for id in ids:
            r = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{id}.json",
                headers=HEADERS, timeout=5
            )
            d = r.json()
            items.append({
                "title": d.get("title", ""),
                "url": d.get("url", f"https://news.ycombinator.com/item?id={id}"),
                "summary": "",
                "source": "Hacker News",
            })
    except Exception as e:
        print(f"  [HN API 降级失败]: {e}")
    return items


def _fetch_v2ex_api() -> list:
    """V2Ex 官方 API 降级方案"""
    items = []
    try:
        resp = requests.get(
            "https://www.v2ex.com/api/topics/latest.json",
            headers=HEADERS, timeout=10
        )
        for t in resp.json()[:10]:
            items.append({
                "title": t.get("title", ""),
                "url": t.get("url", ""),
                "summary": t.get("content", "")[:200] if t.get("content") else "",
                "source": "V2Ex",
            })
    except Exception as e:
        print(f"  [V2Ex API 降级失败]: {e}")
    return items


def fetch_all(max_items: int = 20) -> list:
    """抓取多个真实信息源，合并去重后返回。

    优先用多源 RSS（海外+国内），全部失败则降级到官方 API。

    Args:
        max_items: 最大返回条数

    Returns:
        资讯列表，每条含 title/url/summary/source
    """
    all_items = []

    for src in RSS_SOURCES:
        print(f"  正在抓取 {src['name']}...")
        items = _fetch_rss(src["url"], src["source"])
        if items:
            print(f"    ✅ 获取 {len(items)} 条")
        all_items.extend(items)
        time.sleep(0.3)

    # 降级：如果稳定 RSS 全部失败，使用官方 API
    if not all_items:
        print("  RSS 抓取失败，降级到 Hacker News / V2Ex 官方 API...")
        all_items.extend(_fetch_hn_api())
        all_items.extend(_fetch_v2ex_api())

    # 去重（按标题前 50 字符）
    seen = set()
    unique = []
    for it in all_items:
        key = it["title"][:50]
        if key not in seen:
            seen.add(key)
            unique.append(it)

    # 均分各来源，保证多源覆盖（避免全是第一个来源）
    # 轮询从每个来源取 1 条，直到取满 max_items 或所有来源取完
    from collections import OrderedDict
    by_source = OrderedDict()
    for it in unique:
        by_source.setdefault(it["source"], []).append(it)

    result = []
    # 轮询取条目
    queues = list(by_source.values())
    idx = 0
    while len(result) < max_items and queues:
        all_empty = True
        for q in queues:
            if idx < len(q):
                result.append(q[idx])
                all_empty = False
                if len(result) >= max_items:
                    break
        if all_empty:
            break
        idx += 1

    return result


def fetch_hot_topics() -> list:
    """抓取热门话题榜，确保多来源覆盖。

    优先用稳定 RSS 源（HN/TechCrunch/InfoQ/GitHub）保证基础覆盖，
    再尝试 RSSHub 中文热榜（知乎/微博/百度）补充中文热点。
    全部失败时用 HN API 兜底。

    Returns:
        话题列表，每条含 title/source/url
    """
    topics = []

    # 1) 先抓稳定 RSS 源（已验证可用，保证多来源基础覆盖）
    for src in RSS_SOURCES:
        print(f"  正在抓取 {src['name']}...")
        items = _fetch_rss(src["url"], src["source"])
        for it in items[:8]:  # 每源最多取 8 条，避免单一来源占满
            topics.append({
                "title": it["title"],
                "source": it["source"],
                "url": it["url"],
            })
        time.sleep(0.3)

    # 2) 再尝试 RSSHub 中文热榜（补充中文热点，失败不影响已有结果）
    for src in HOT_TOPIC_ROUTES:
        print(f"  正在抓取 {src['name']}...")
        items = _fetch_rsshub_with_fallback(src["route"], src["source"])
        for it in items[:8]:
            topics.append({
                "title": it["title"],
                "source": it["source"],
                "url": it["url"],
            })
        time.sleep(0.3)

    # 3) 补充 V2Ex 热门话题（直接 RSS，不走 RSSHub）
    for src in V2EX_HOT_NODES:
        print(f"  正在抓取 {src['name']}...")
        items = _fetch_rss(src["url"], src["source"])
        for it in items[:8]:
            topics.append({
                "title": it["title"],
                "source": it["source"],
                "url": it["url"],
            })
        time.sleep(0.3)

    # 4) 降级：如果全部失败，用 HN API 兜底
    if not topics:
        print("  热门话题榜不可用，启用备用源（Hacker News 热门）...")
        topics = _fetch_hn_api()

    # 去重 + 均分各来源
    seen = set()
    unique = []
    for it in topics:
        key = it["title"][:50]
        if key not in seen:
            seen.add(key)
            unique.append(it)

    from collections import OrderedDict
    by_source = OrderedDict()
    for it in unique:
        by_source.setdefault(it["source"], []).append(it)

    result = []
    queues = list(by_source.values())
    idx = 0
    while len(result) < 30 and queues:
        all_empty = True
        for q in queues:
            if idx < len(q):
                result.append(q[idx])
                all_empty = False
                if len(result) >= 30:
                    break
        if all_empty:
            break
        idx += 1

    return result

import datetime
import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests


API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DAILY_LIMIT = 30
MAX_RECORDS = 1000

SMARTBUILD_TERMS = [
    "智能建造", "智慧工地", "建筑机器人", "装配式建筑", "BIM", "城市更新",
    "好房子", "新型建筑工业化", "数字化施工", "无人施工",
]

SEARCH_QUERIES = [
    {"query": "智能建造", "category": "行业动态"},
    {"query": "智能建造 政策 OR 试点 OR 住建局", "category": "政策"},
    {"query": "智能建造 招标 OR 中标 OR 采购", "category": "招采"},
    {"query": "智慧工地 平台 OR 中标 OR 项目", "category": "智慧工地"},
    {"query": "建筑机器人 采购 OR 应用 OR 项目", "category": "建筑机器人"},
    {"query": "装配式建筑 智能建造 OR 政策", "category": "装配式建筑"},
    {"query": "BIM AI 建筑 OR 施工", "category": "BIM+AI"},
    {"query": "好房子 标准 智能建造", "category": "好房子"},
    {"query": "城市更新 智能建造", "category": "城市更新"},
]

DOMESTIC_LIST_SOURCES = [
    {
        "name": "住房城乡建设部",
        "url": "https://www.mohurd.gov.cn/gongkai/zc/wjk/index.html",
        "category": "政策",
    },
    {
        "name": "住房城乡建设部",
        "url": "https://www.mohurd.gov.cn/xinwen/gzdt/index.html",
        "category": "行业动态",
    },
    {
        "name": "中国政府网政策库",
        "url": "https://www.gov.cn/zhengce/zhengceku/",
        "category": "政策",
    },
    {
        "name": "全国公共资源交易平台",
        "url": "https://www.ggzy.gov.cn/information/html/a/0101/list.html",
        "category": "招采",
    },
]

DOMESTIC_SEARCH_SOURCES = [
    {
        "name": "中国政府采购网",
        "url": "https://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0&buyerName=&projectId=&pinMu=0&bidType=0&dbselect=bidx&kw={query}&start_time=&end_time=&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName=",
        "category": "招采",
        "queries": ["智能建造", "智慧工地", "建筑机器人", "BIM 建筑"],
    },
]

REGION_KEYWORDS = [
    "北京", "上海", "深圳", "广州", "江苏", "浙江", "广东", "重庆", "四川",
    "湖北", "湖南", "河南", "山东", "安徽", "陕西", "雄安", "南京", "苏州",
    "杭州", "成都", "武汉", "郑州", "长沙", "合肥", "西安", "厦门",
]

LEAD_SIGNALS = {
    "招采": ["招标", "中标", "采购", "成交", "合同", "入围", "遴选"],
    "政策": ["政策", "通知", "意见", "方案", "试点", "规划", "住建", "标准"],
    "项目": ["项目", "开工", "建设", "投产", "示范", "园区", "工程"],
    "企业": ["集团", "公司", "股份", "科技", "建工", "中建", "中铁", "中交"],
    "会议": ["大会", "峰会", "博览会", "交流会", "论坛"],
}

SOURCE_OWNER_HINTS = {
    "北京": "华北销售组",
    "上海": "华东销售一组",
    "江苏": "华东销售二组",
    "浙江": "华东销售二组",
    "苏州": "华东销售二组",
    "南京": "华东销售二组",
    "杭州": "华东销售二组",
    "深圳": "华南销售一组",
    "广州": "华南销售一组",
    "广东": "华南销售一组",
    "厦门": "华南销售二组",
    "四川": "西南销售组",
    "成都": "西南销售组",
    "重庆": "西南销售组",
    "湖北": "华中销售组",
    "湖南": "华中销售组",
    "武汉": "华中销售组",
    "长沙": "华中销售组",
    "河南": "华中销售组",
    "郑州": "华中销售组",
}

REGION_GROUPS = {
    "华北": ["北京", "天津", "河北", "雄安"],
    "华东": ["上海", "江苏", "浙江", "安徽", "山东", "南京", "苏州", "杭州", "合肥"],
    "华南": ["广东", "深圳", "广州", "厦门", "福建", "广西", "海南"],
    "华中": ["湖北", "湖南", "河南", "武汉", "长沙", "郑州"],
    "西南": ["四川", "重庆", "成都", "贵州", "云南"],
    "西北": ["陕西", "西安", "甘肃", "宁夏", "新疆", "青海"],
}


def parse_date(pub_date):
    if not pub_date:
        return datetime.date.today().strftime("%Y-%m-%d")
    try:
        dt = datetime.datetime.strptime(pub_date[:16], "%a, %d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return datetime.date.today().strftime("%Y-%m-%d")


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def split_title_source(raw_title):
    title = raw_title or ""
    source = "行业资讯"
    if " - " in title:
        title, source = title.rsplit(" - ", 1)
    elif "-" in title:
        title, source = title.rsplit("-", 1)
    return title.strip(), source.strip()


def clean_title(value):
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n\t-_|")


def is_relevant(title):
    return any(term.lower() in title.lower() for term in SMARTBUILD_TERMS)


def baidu_search_link(title):
    return "https://www.baidu.com/s?wd=" + urllib.parse.quote_plus(title)


def source_search_link(source, title):
    if source == "中国政府采购网":
        return DOMESTIC_SEARCH_SOURCES[0]["url"].format(query=urllib.parse.quote_plus(title))
    if source == "全国公共资源交易平台":
        return "https://www.ggzy.gov.cn/search/index.html?keyword=" + urllib.parse.quote_plus(title)
    return baidu_search_link(title)


def detect_sales_region(region):
    for group, names in REGION_GROUPS.items():
        if any(name in region for name in names):
            return group
    return "全国"


def detect_owner(region):
    for key, owner in SOURCE_OWNER_HINTS.items():
        if key in region:
            return owner
    return "市场线索池"


def normalize_link(url, base_url):
    if not url:
        return ""
    url = html.unescape(url)
    if url.startswith("javascript:") or url.startswith("#"):
        return ""
    return urllib.parse.urljoin(base_url, url)


def make_item(title, link, source, category, date=None, keyword="", channel="国内直连"):
    title = clean_title(title)
    if not title:
        return None

    region = detect_region(title)
    direct = bool(link and "news.google.com" not in link)
    search_link = source_search_link(source, title)
    return {
        "title": title,
        "link": link or search_link,
        "original_link": link if direct else "",
        "search_link": search_link,
        "date": date or today_str(),
        "source": source,
        "keyword": keyword,
        "category": detect_category(title, category),
        "region": region,
        "sales_region": detect_sales_region(region),
        "owner": detect_owner(region),
        "source_channel": channel,
        "source_access": "domestic_direct" if direct else "search_required",
        "link_status": "原文可直达" if direct else "需搜索核查",
    }


def extract_html_links(content, base_url):
    links = []
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", content, re.I | re.S):
        url = normalize_link(match.group(1), base_url)
        title = clean_title(match.group(2))
        if url and title:
            links.append((title, url))
    return links


def fetch_html(url, headers):
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return resp.text


def fetch_domestic_lists(headers):
    items = []
    for source in DOMESTIC_LIST_SOURCES:
        try:
            content = fetch_html(source["url"], headers)
        except Exception as e:
            print(f"国内列表抓取失败 [{source['name']}]: {e}")
            continue

        for title, link in extract_html_links(content, source["url"]):
            if not is_relevant(title):
                continue
            item = make_item(
                title=title,
                link=link,
                source=source["name"],
                category=source["category"],
                keyword="国内直连",
                channel="国内官网",
            )
            if item:
                items.append(item)
            if len(items) >= DAILY_LIMIT:
                return items
        time.sleep(0.5)
    return items


def fetch_domestic_searches(headers):
    items = []
    for source in DOMESTIC_SEARCH_SOURCES:
        for query in source["queries"]:
            url = source["url"].format(query=urllib.parse.quote_plus(query))
            try:
                content = fetch_html(url, headers)
            except Exception as e:
                print(f"国内搜索抓取失败 [{source['name']} {query}]: {e}")
                continue

            for title, link in extract_html_links(content, url):
                if not is_relevant(title):
                    continue
                item = make_item(
                    title=title,
                    link=link,
                    source=source["name"],
                    category=source["category"],
                    keyword=query,
                    channel="国内招采搜索",
                )
                if item:
                    items.append(item)
                if len(items) >= DAILY_LIMIT:
                    return items
            time.sleep(0.5)
    return items


def normalize_google_link(link):
    return {
        "link": link,
        "original_link": "",
        "google_link": link,
        "source_access": "google_rss",
        "link_status": "需搜索核查",
    }


def fetch_google_news():
    print("正在抓取智能建造商业信息...")
    items = []
    seen_links = set()
    headers = {"User-Agent": "Mozilla/5.0"}

    domestic_items = fetch_domestic_lists(headers) + fetch_domestic_searches(headers)
    for item in domestic_items:
        key = item.get("original_link") or item.get("link") or item["title"]
        if key in seen_links:
            continue
        seen_links.add(key)
        items.append(item)

    for config in SEARCH_QUERIES:
        encoded_query = urllib.parse.quote_plus(config["query"])
        url = (
            "https://news.google.com/rss/search?"
            f"q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            print(f"抓取失败 [{config['query']}]: {e}")
            continue

        for node in root.findall("./channel/item")[:12]:
            raw_title = node.findtext("title", default="")
            link = node.findtext("link", default="")
            if not raw_title or not link or link in seen_links:
                continue
            seen_links.add(link)
            title, source = split_title_source(raw_title)
            links = normalize_google_link(link)
            items.append({
                "title": title,
                "link": links["link"],
                "original_link": links["original_link"],
                "google_link": links["google_link"],
                "search_link": baidu_search_link(title),
                "date": parse_date(node.findtext("pubDate", default="")),
                "source": source,
                "keyword": config["query"],
                "category": config["category"],
                "source_channel": "Google News RSS",
                "source_access": links["source_access"],
                "link_status": links["link_status"],
            })
        time.sleep(0.5)

    return rank_candidates(items)


def detect_region(title):
    for region in REGION_KEYWORDS:
        if region in title:
            return region
    return "全国"


def detect_category(title, fallback):
    for category, words in LEAD_SIGNALS.items():
        if any(word in title for word in words):
            return category
    return fallback or "行业动态"


def score_item(title, category):
    score = 2
    if category in ["招采", "政策"]:
        score += 2
    elif category in ["项目", "企业"]:
        score += 1
    if any(word in title for word in ["招标", "中标", "采购", "入围", "试点", "示范", "专项", "规划"]):
        score += 1
    return min(score, 5)


def fallback_insight(item):
    title = item["title"]
    category = detect_category(title, item.get("category"))
    region = detect_region(title)
    score = score_item(title, category)

    action = "跟进原文主体、所在地住建部门及后续招采/试点名单。"
    if category == "招采":
        action = "核查招标/中标主体、预算金额、采购需求和联系人，评估可切入产品。"
    elif category == "政策":
        action = "跟进政策配套细则、试点申报窗口和重点承接单位。"
    elif category == "项目":
        action = "识别项目业主、总包单位和智能化应用场景，准备拜访线索。"

    return {
        "summary": title[:80],
        "category": category,
        "region": region,
        "sales_region": item.get("sales_region") or detect_sales_region(region),
        "owner": item.get("owner") or detect_owner(region),
        "entities": [],
        "business_value": "可作为智能建造、智慧工地、建筑机器人或数字化施工相关市场机会观察点。",
        "lead_score": score,
        "lead_reason": f"{category}信号明确，可能带来项目、试点或合作机会。",
        "suggested_action": action,
        "urgency": "中",
    }


def clean_json_text(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else text


def call_ai_insight(item):
    fallback = fallback_insight(item)
    if not API_KEY:
        return fallback

    url = "https://api.deepseek.com/chat/completions"
    system_prompt = (
        "你是智能建造领域的商业情报分析师。只基于给定新闻标题和来源做判断，"
        "输出严格 JSON，不要 Markdown。目标是帮助销售、市场和战略团队识别商业 leads。"
    )
    user_prompt = f"""
新闻标题：{item['title']}
来源：{item.get('source', '')}
关键词：{item.get('keyword', '')}

请输出 JSON，字段如下：
- summary: 40字以内事实摘要
- category: 政策/招采/项目/企业/标准/会议/技术/行业动态 之一
- region: 涉及地区，不明确则写 全国
- entities: 相关机构、企业或项目名称数组
- business_value: 60字以内，说明对供应商/咨询/系统集成/建筑科技公司的商业价值
- lead_score: 1-5，5代表很值得马上跟进
- lead_reason: 50字以内，说明评分原因
- suggested_action: 50字以内，给出下一步跟进行动
- urgency: 高/中/低
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            print(f"AI接口返回异常: {res.status_code}")
            return fallback

        content = res.json()["choices"][0]["message"]["content"]
        parsed = json.loads(clean_json_text(content))
        fallback.update({
            "summary": parsed.get("summary") or fallback["summary"],
            "category": parsed.get("category") or fallback["category"],
            "region": parsed.get("region") or fallback["region"],
            "entities": parsed.get("entities") if isinstance(parsed.get("entities"), list) else fallback["entities"],
            "business_value": parsed.get("business_value") or fallback["business_value"],
            "lead_score": int(parsed.get("lead_score") or fallback["lead_score"]),
            "lead_reason": parsed.get("lead_reason") or fallback["lead_reason"],
            "suggested_action": parsed.get("suggested_action") or fallback["suggested_action"],
            "urgency": parsed.get("urgency") or fallback["urgency"],
        })
        fallback["lead_score"] = max(1, min(5, fallback["lead_score"]))
        return fallback
    except Exception as e:
        print(f"AI分析失败: {e}")
        return fallback


def rank_candidates(items):
    def rank_key(item):
        insight = fallback_insight(item)
        return (insight["lead_score"], item["date"])

    return sorted(items, key=rank_key, reverse=True)


def load_old_data():
    if not os.path.exists("data.json"):
        return []
    with open("data.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def job():
    new_items = fetch_google_news()
    old_data = load_old_data()
    existing_titles = {item.get("title", "") for item in old_data}
    existing_links = {item.get("link", "") for item in old_data}
    final_data = old_data[:]

    count = 0
    for item in new_items:
        if item["title"] in existing_titles or item["link"] in existing_links:
            continue

        print(f"正在生成商业洞察: {item['title'][:24]}...")
        insight = call_ai_insight(item)
        item.update(insight)
        item["sales_region"] = item.get("sales_region") or detect_sales_region(item.get("region", "全国"))
        item["owner"] = item.get("owner") or detect_owner(item.get("region", "全国"))
        item["search_link"] = item.get("search_link") or baidu_search_link(item["title"])
        item["link_status"] = item.get("link_status") or (
            "原文可直达" if item.get("original_link") else "需搜索核查"
        )
        item["updated_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        final_data.insert(0, item)
        count += 1

        if count >= DAILY_LIMIT:
            break
        time.sleep(0.8)

    final_data = sorted(final_data, key=lambda x: (x.get("date", ""), x.get("lead_score", 0)), reverse=True)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_data[:MAX_RECORDS], f, ensure_ascii=False, indent=2)

    print(f"今日更新完成，新增 {count} 条商业线索，当前最多留存 {MAX_RECORDS} 条。")


if __name__ == "__main__":
    job()

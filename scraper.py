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
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "70"))
MIN_QUALITY_SCORE = int(os.environ.get("MIN_QUALITY_SCORE", "3"))
RSS_ITEMS_PER_QUERY = int(os.environ.get("RSS_ITEMS_PER_QUERY", "40"))
MAX_RECORDS = int(os.environ.get("MAX_RECORDS", "5000"))
MAX_SOURCE_AGE_DAYS = int(os.environ.get("MAX_SOURCE_AGE_DAYS", "180"))
GOOGLE_NEWS_LOOKBACK_DAYS = int(os.environ.get("GOOGLE_NEWS_LOOKBACK_DAYS", "30"))
NEWS_ONLY = os.environ.get("NEWS_ONLY", "1") != "0"

SMARTBUILD_TERMS = [
    "智能建造", "智慧工地", "建筑机器人", "装配式建筑", "BIM", "城市更新",
    "好房子", "新型建筑工业化", "数字化施工", "无人施工", "智慧建造",
    "施工机器人", "工地监管", "CIM", "BIM审图", "AI质检", "实测实量",
]

STRONG_FIT_TERMS = [
    "智能建造", "智慧工地", "建筑机器人", "BIM", "好房子",
    "新型建筑工业化", "数字化施工", "无人施工", "装配式建筑",
    "施工机器人", "智慧建造", "建筑工业化", "机器人施工", "工地监管",
    "BIM审图", "AI质检", "实测实量",
]

SEARCH_QUERIES = [
    {"query": "\"智慧工地\" 招标 OR 中标 OR 成交 OR 采购 OR 合同", "category": "招采", "priority": 5},
    {"query": "\"智能建造\" 招标 OR 中标 OR 成交 OR 采购 OR 合同", "category": "招采", "priority": 5},
    {"query": "\"建筑机器人\" 采购 OR 中标 OR 应用 OR 项目 OR 进场", "category": "建筑机器人", "priority": 5},
    {"query": "\"施工机器人\" 采购 OR 中标 OR 应用 OR 项目", "category": "建筑机器人", "priority": 5},
    {"query": "\"BIM\" 建筑 招标 OR 中标 OR 采购 OR 审图 OR 施工", "category": "BIM+AI", "priority": 4},
    {"query": "住建厅 智能建造 OR 智慧工地 OR 好房子 试点 OR 通知 OR 方案", "category": "政策", "priority": 5},
    {"query": "住建局 智能建造 OR 智慧工地 OR 好房子 试点 OR 通知 OR 方案", "category": "政策", "priority": 5},
    {"query": "\"智能建造试点\" 项目 OR 名单 OR 公示 OR 示范", "category": "政策", "priority": 5},
    {"query": "\"好房子\" 智能建造 OR 装配式 OR 建筑机器人 OR 智慧工地", "category": "好房子", "priority": 4},
    {"query": "\"新型建筑工业化\" 政策 OR 试点 OR 项目 OR 示范", "category": "装配式建筑", "priority": 4},
    {"query": "\"城市更新\" 智慧工地 OR 智能建造 OR BIM OR 数字化施工", "category": "城市更新", "priority": 3},
    {"query": "城投 智慧工地 OR 智能建造 OR 数字化施工 OR BIM", "category": "项目", "priority": 4},
    {"query": "建工集团 智慧工地 OR 建筑机器人 OR 智能建造 OR 数字化施工", "category": "企业", "priority": 4},
    {"query": "中建 智慧工地 OR 建筑机器人 OR 智能建造 OR 数字化施工", "category": "企业", "priority": 4},
    {"query": "博智林 OR 博匠机器人 OR 领鹊科技 OR 德睿途 建筑机器人 OR 智能建造", "category": "竞对动态", "priority": 3},
    {"query": "建科智能 OR 河狸智造 OR 方石科技 OR 丰坦科技 OR 南京湃特纳", "category": "竞对动态", "priority": 3},
]

OPPORTUNITY_SIGNAL_TERMS = [
    "招标", "中标", "成交", "采购", "合同", "入围", "遴选", "预算",
    "试点", "示范", "名单", "公示", "通知", "方案", "规划",
    "项目", "开工", "建设", "进场", "应用", "落地", "上线",
    "住建厅", "住建局", "城投", "建工", "中建", "中铁", "中交",
    "签约", "合作", "发布", "新品", "解决方案", "融资", "获奖", "推广",
]

LOW_VALUE_TITLE_TERMS = [
    "论文", "课程", "培训", "招聘", "考试", "真题", "招生", "专业介绍",
    "股票", "股价", "概念股", "龙头股", "涨停", "研报", "股吧",
    "排行榜", "十大", "毕业设计", "专利", "下载", "模板",
]

COMPETITOR_TERMS = [
    "博智林", "博匠机器人", "领鹊科技", "德睿途", "建科智能",
    "河狸智造", "方石科技", "丰坦科技", "南京湃特纳",
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

ORG_WEBSITE_SOURCES = [
    {
        "name": "中国建筑集团",
        "url": "https://www.cscec.com/xwzx_new/gsyw_new/",
        "category": "企业",
        "group": "央国企官网",
    },
    {
        "name": "上海建工",
        "url": "https://www.scg.com.cn/scg_zxzx/qydt/",
        "category": "企业",
        "group": "建工企业官网",
    },
    {
        "name": "北京建工",
        "url": "https://www.bcegc.com/xwzx/qydt/",
        "category": "企业",
        "group": "建工企业官网",
    },
    {
        "name": "中国施工企业管理协会",
        "url": "https://www.cacem.com.cn/",
        "category": "行业动态",
        "group": "协会官网",
    },
    {
        "name": "中国建筑业协会",
        "url": "https://www.zgjzy.org.cn/",
        "category": "行业动态",
        "group": "协会官网",
    },
]

WECHAT_MONITOR_ACCOUNTS = [
    {"name": "中国建设报", "priority": "P0", "type": "政策/行业"},
    {"name": "中国建设报智慧城市", "priority": "P0", "type": "政策/行业"},
    {"name": "安居北京", "priority": "P0", "type": "地方住建"},
    {"name": "中国施工企业管理协会", "priority": "P0", "type": "协会"},
    {"name": "中国建筑业协会", "priority": "P0", "type": "协会"},
    {"name": "建筑时报", "priority": "P0", "type": "行业媒体"},
    {"name": "中国建筑", "priority": "P0", "type": "央国企"},
    {"name": "中建科技", "priority": "P0", "type": "央国企"},
    {"name": "中建智能", "priority": "P0", "type": "央国企"},
    {"name": "中国交建", "priority": "P0", "type": "央国企"},
    {"name": "上海住房城乡建设管理", "priority": "P1", "type": "地方住建"},
    {"name": "江苏住建", "priority": "P1", "type": "地方住建"},
    {"name": "浙江建设", "priority": "P1", "type": "地方住建"},
    {"name": "广东建设信息", "priority": "P1", "type": "地方住建"},
    {"name": "深圳住建", "priority": "P1", "type": "地方住建"},
    {"name": "武汉住建", "priority": "P1", "type": "地方住建"},
    {"name": "湖北住建", "priority": "P1", "type": "地方住建"},
    {"name": "湖南住建", "priority": "P1", "type": "地方住建"},
    {"name": "四川建设发布", "priority": "P1", "type": "地方住建"},
    {"name": "重庆住建", "priority": "P1", "type": "地方住建"},
    {"name": "中建三局", "priority": "P1", "type": "建工客户"},
    {"name": "中建八局", "priority": "P1", "type": "建工客户"},
    {"name": "上海建工", "priority": "P1", "type": "建工客户"},
    {"name": "北京建工", "priority": "P1", "type": "建工客户"},
    {"name": "博智林", "priority": "P1", "type": "竞对"},
    {"name": "博匠机器人", "priority": "P1", "type": "竞对"},
    {"name": "领鹊科技", "priority": "P1", "type": "竞对"},
    {"name": "德睿途", "priority": "P1", "type": "竞对"},
    {"name": "建科智能", "priority": "P1", "type": "竞对"},
    {"name": "河狸智造", "priority": "P1", "type": "竞对"},
    {"name": "方石科技", "priority": "P1", "type": "竞对"},
    {"name": "丰坦科技", "priority": "P1", "type": "竞对"},
    {"name": "南京湃特纳", "priority": "P1", "type": "竞对"},
]

WECHAT_MONITOR_TERMS = [
    "智能建造",
    "建筑机器人",
    "智慧工地",
    "好房子",
    "新型建筑工业化",
]

REGION_KEYWORDS = [
    "北京", "上海", "深圳", "广州", "江苏", "浙江", "广东", "重庆", "四川",
    "湖北", "湖南", "河南", "山东", "安徽", "陕西", "雄安", "南京", "苏州",
    "杭州", "成都", "武汉", "郑州", "长沙", "合肥", "西安", "厦门",
    "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "福建",
    "江西", "广西", "海南", "贵州", "云南", "西藏", "甘肃", "青海",
    "宁夏", "新疆", "佛山", "东莞", "珠海", "青岛", "济南", "宁波",
    "无锡", "常州", "温州", "南昌", "福州", "昆明", "贵阳", "南宁",
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


def parse_date(pub_date, default=""):
    if not pub_date:
        return default
    try:
        dt = datetime.datetime.strptime(pub_date[:16], "%a, %d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return default


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def now_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


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


def is_low_value_title(title):
    return any(term.lower() in title.lower() for term in LOW_VALUE_TITLE_TERMS)


def has_opportunity_signal(title):
    return any(term.lower() in title.lower() for term in OPPORTUNITY_SIGNAL_TERMS)


def has_competitor_signal(title):
    return any(term.lower() in title.lower() for term in COMPETITOR_TERMS)


def is_search_candidate(title, category):
    if is_low_value_title(title):
        return False
    if category == "竞对动态":
        return has_competitor_signal(title) and (is_relevant(title) or has_opportunity_signal(title))
    if is_relevant(title) and has_opportunity_signal(title):
        return True
    if category in ["招采", "政策", "项目", "竞对动态"] and is_relevant(title):
        return True
    return False


def is_strong_fit(item):
    text = " ".join([
        item.get("title", ""),
        item.get("summary", ""),
        item.get("business_value", ""),
        item.get("category", ""),
        " ".join(item.get("entities", []) if isinstance(item.get("entities"), list) else []),
    ])
    return any(term.lower() in text.lower() for term in STRONG_FIT_TERMS)


def baidu_search_link(title):
    return "https://www.baidu.com/s?wd=" + urllib.parse.quote_plus(title)


def source_search_link(source, title):
    if source == "中国政府采购网":
        return DOMESTIC_SEARCH_SOURCES[0]["url"].format(query=urllib.parse.quote_plus(title))
    if source == "全国公共资源交易平台":
        return "https://www.ggzy.gov.cn/search/index.html?keyword=" + urllib.parse.quote_plus(title)
    return baidu_search_link(title)


def load_wechat_accounts():
    accounts_json = os.environ.get("WECHAT_ACCOUNTS_JSON", "")
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
            if isinstance(accounts, list):
                return [
                    account for account in accounts
                    if account.get("app_id") and account.get("app_secret")
                ]
        except Exception as e:
            print(f"微信公众号账号配置解析失败: {e}")

    app_id = os.environ.get("WECHAT_APP_ID")
    app_secret = os.environ.get("WECHAT_APP_SECRET")
    if app_id and app_secret:
        return [{
            "name": os.environ.get("WECHAT_ACCOUNT_NAME", "微信公众号"),
            "app_id": app_id,
            "app_secret": app_secret,
        }]
    return []


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
    source_date = date or ""
    return {
        "title": title,
        "link": link or search_link,
        "original_link": link if direct else "",
        "search_link": search_link,
        "date": source_date,
        "published_date": source_date,
        "source_date": source_date,
        "collected_at": now_iso(),
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


def extract_page_title(content):
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.I | re.S)
        if match:
            return clean_title(match.group(1))
    return ""


def parse_sogou_date(value):
    text = clean_title(value)
    if not text:
        return ""
    today = datetime.date.today()
    if "小时前" in text or "分钟前" in text or "今天" in text:
        return today.strftime("%Y-%m-%d")
    if "昨天" in text:
        return (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    match = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        month, day = match.groups()
        return f"{today.year}-{int(month):02d}-{int(day):02d}"
    return ""


def sogou_wechat_url(account, term):
    query = f'{account} {term}'
    return "https://weixin.sogou.com/weixin?type=2&query=" + urllib.parse.quote_plus(query)


def extract_sogou_wechat_articles(content, base_url):
    articles = []
    blocks = re.findall(r'<li[^>]*id=["\']sogou_vr_11002601_box_\d+["\'][^>]*>(.*?)</li>', content, re.I | re.S)
    if not blocks:
        blocks = re.findall(r'<div[^>]+class=["\'][^"\']*txt-box[^"\']*["\'][^>]*>(.*?)</div>', content, re.I | re.S)

    for block in blocks:
        link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, re.I | re.S)
        if not link_match:
            continue
        link = normalize_link(link_match.group(1), base_url)
        title = clean_title(link_match.group(2))
        if "mp.weixin.qq.com" not in link or not title:
            continue

        account_match = re.search(r'<a[^>]+class=["\'][^"\']*account[^"\']*["\'][^>]*>(.*?)</a>', block, re.I | re.S)
        date_match = re.search(r'<span[^>]+class=["\'][^"\']*s2[^"\']*["\'][^>]*>(.*?)</span>', block, re.I | re.S)
        articles.append({
            "title": title,
            "link": link,
            "account": clean_title(account_match.group(1)) if account_match else "",
            "date": parse_sogou_date(date_match.group(1)) if date_match else "",
        })
    return articles


def fetch_html(url, headers):
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return resp.text


def extract_source_date(content):
    patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
        r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']publishdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r"发布时间[:：]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"发布日期[:：]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"发文日期[:：]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"公告日期[:：]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.I | re.S)
        if match:
            return normalize_date_text(match.group(1))
    return ""


def normalize_date_text(value):
    text = clean_title(value)
    match = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})T", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return ""


def fetch_source_date(url, headers):
    if not url or "news.google.com" in url:
        return ""
    try:
        content = fetch_html(url, headers)
    except Exception:
        return ""
    return extract_source_date(content)


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
            source_date = fetch_source_date(link, headers)
            item = make_item(
                title=title,
                link=link,
                source=source["name"],
                category=source["category"],
                date=source_date,
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
                source_date = fetch_source_date(link, headers)
                item = make_item(
                    title=title,
                    link=link,
                    source=source["name"],
                    category=source["category"],
                    date=source_date,
                    keyword=query,
                    channel="国内招采搜索",
                )
                if item:
                    items.append(item)
                if len(items) >= DAILY_LIMIT:
                    return items
            time.sleep(0.5)
    return items


def fetch_org_websites(headers):
    items = []
    for source in ORG_WEBSITE_SOURCES:
        try:
            content = fetch_html(source["url"], headers)
        except Exception as e:
            print(f"机构官网抓取失败 [{source['name']}]: {e}")
            continue

        for title, link in extract_html_links(content, source["url"]):
            if not is_relevant(title):
                continue
            source_date = fetch_source_date(link, headers)
            item = make_item(
                title=title,
                link=link,
                source=source["name"],
                category=source["category"],
                date=source_date,
                keyword=source["group"],
                channel=source["group"],
            )
            if item:
                items.append(item)
            if len(items) >= DAILY_LIMIT:
                return items
        time.sleep(0.5)
    return items


def fetch_wechat_access_token(account):
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": account["app_id"],
        "secret": account["app_secret"],
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(data.get("errmsg") or "未返回 access_token")
    return token


def parse_wechat_news_item(news, account_name, fallback_time=None):
    title = clean_title(news.get("title", ""))
    url = news.get("url") or news.get("content_source_url") or ""
    if not title or not url:
        return None
    item = make_item(
        title=title,
        link=url,
        source=account_name,
        category=detect_category(title, "行业动态"),
        keyword="微信公众号",
        channel="微信公众号文章",
    )
    if item:
        digest = clean_title(news.get("digest", ""))
        if digest:
            item["summary"] = digest
        if fallback_time:
            item["date"] = datetime.datetime.fromtimestamp(fallback_time).strftime("%Y-%m-%d")
    return item


def fetch_wechat_freepublish(token, account_name):
    items = []
    url = "https://api.weixin.qq.com/cgi-bin/freepublish/batchget"
    for offset in range(0, 40, 20):
        try:
            resp = requests.post(
                f"{url}?access_token={token}",
                json={"offset": offset, "count": 20, "no_content": 1},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"微信公众号已发布文章抓取失败 [{account_name}]: {e}")
            continue

        for record in data.get("item", []):
            content = record.get("content", {})
            for news in content.get("news_item", []):
                item = parse_wechat_news_item(news, account_name, record.get("publish_time") or record.get("update_time"))
                if item and is_relevant(item["title"]):
                    items.append(item)
        if data.get("item_count", 0) < 20:
            break
    return items


def fetch_wechat_materials(token, account_name):
    items = []
    url = "https://api.weixin.qq.com/cgi-bin/material/batchget_material"
    for offset in range(0, 40, 20):
        try:
            resp = requests.post(
                f"{url}?access_token={token}",
                json={"type": "news", "offset": offset, "count": 20},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"微信公众号素材抓取失败 [{account_name}]: {e}")
            continue

        for record in data.get("item", []):
            content = record.get("content", {})
            for news in content.get("news_item", []):
                item = parse_wechat_news_item(news, account_name, record.get("update_time"))
                if item and is_relevant(item["title"]):
                    items.append(item)
        if data.get("item_count", 0) < 20:
            break
    return items


def fetch_wechat_articles(headers):
    items = []
    accounts = load_wechat_accounts()
    for account in accounts:
        account_name = account.get("name", "微信公众号")
        try:
            token = fetch_wechat_access_token(account)
        except Exception as e:
            print(f"微信公众号 access_token 获取失败 [{account_name}]: {e}")
            continue

        items.extend(fetch_wechat_freepublish(token, account_name))
        items.extend(fetch_wechat_materials(token, account_name))
        time.sleep(0.5)

    seen = {item["link"] for item in items}
    for account in WECHAT_MONITOR_ACCOUNTS:
        for term in WECHAT_MONITOR_TERMS:
            search_url = sogou_wechat_url(account["name"], term)
            try:
                content = fetch_html(search_url, headers)
            except Exception as e:
                print(f"微信公众号号池搜索失败 [{account['name']} {term}]: {e}")
                continue

            if "请输入验证码" in content or "antispider" in content.lower():
                print(f"微信公众号号池搜索触发验证码 [{account['name']} {term}]")
                continue

            for article in extract_sogou_wechat_articles(content, search_url)[:3]:
                if article["link"] in seen or not is_relevant(article["title"]):
                    continue
                seen.add(article["link"])
                source_name = article["account"] or account["name"]
                item = make_item(
                    title=article["title"],
                    link=article["link"],
                    source=source_name,
                    category=detect_category(article["title"], "行业动态"),
                    date=article["date"],
                    keyword=f"{account['name']} {term}",
                    channel=f"微信公众号号池/{account['type']}",
                )
                if item:
                    item["wechat_account"] = account["name"]
                    item["wechat_priority"] = account["priority"]
                    items.append(item)
                if len(items) >= DAILY_LIMIT:
                    return items
            time.sleep(0.8)
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
    mode = "新闻搜索模式" if NEWS_ONLY else "全源模式"
    print(f"正在抓取智能建造商业信息... 当前模式：{mode}")
    items = []
    seen_links = set()
    headers = {"User-Agent": "Mozilla/5.0"}

    if not NEWS_ONLY:
        domestic_items = (
            fetch_domestic_lists(headers)
            + fetch_domestic_searches(headers)
            + fetch_org_websites(headers)
            + fetch_wechat_articles(headers)
        )
        for item in domestic_items:
            key = item.get("original_link") or item.get("link") or item["title"]
            if key in seen_links:
                continue
            seen_links.add(key)
            items.append(item)

    for config in SEARCH_QUERIES:
        encoded_query = urllib.parse.quote_plus(
            f"{config['query']} when:{GOOGLE_NEWS_LOOKBACK_DAYS}d"
        )
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

        for node in root.findall("./channel/item")[:RSS_ITEMS_PER_QUERY]:
            raw_title = node.findtext("title", default="")
            link = node.findtext("link", default="")
            if not raw_title or not link or link in seen_links:
                continue
            seen_links.add(link)
            title, source = split_title_source(raw_title)
            if not is_search_candidate(title, config["category"]):
                continue
            search_link = baidu_search_link(title)
            links = normalize_google_link(link)
            items.append({
                "title": title,
                "link": search_link,
                "original_link": links["original_link"],
                "google_link": links["google_link"],
                "search_link": search_link,
                "date": parse_date(node.findtext("pubDate", default="")),
                "published_date": parse_date(node.findtext("pubDate", default="")),
                "source_date": parse_date(node.findtext("pubDate", default="")),
                "collected_at": now_iso(),
                "source": source,
                "keyword": config["query"],
                "search_priority": config.get("priority", 3),
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
    return sales_score_factors({"title": title, "category": category})["lead_score"]


def factor(value, reason):
    return {"score": max(0, min(5, int(value))), "reason": reason}


def sales_score_factors(item):
    text = " ".join([
        item.get("title", ""),
        item.get("summary", ""),
        item.get("business_value", ""),
        " ".join(item.get("entities", []) if isinstance(item.get("entities"), list) else []),
    ])
    category = detect_category(text, item.get("category"))
    region = item.get("sales_region") or detect_sales_region(item.get("region") or detect_region(text))
    source_access = item.get("source_access", "")
    link_status = item.get("link_status", "")
    channel = item.get("source_channel", "")
    source = item.get("source", "")
    published_date = item.get("published_date") or item.get("date", "")

    direct_source = source_access == "domestic_direct" or link_status == "原文可直达"
    official_source = any(name in f"{source} {channel}" for name in ["政府", "住建", "公共资源", "采购网", "官网", "协会"])
    if direct_source and official_source:
        source_factor = factor(5, "原文直连且来源为政府/招采/官网/协会等可信渠道")
    elif direct_source:
        source_factor = factor(4, "原文可直达，来源可信度较高")
    elif source_access == "google_rss":
        source_factor = factor(3, "来自 Google RSS，需通过搜索原文核查出处")
    else:
        source_factor = factor(3, "来源可用，但仍需核查出处")

    if category == "招采" or any(word in text for word in ["招标", "中标", "采购", "成交", "合同", "入围", "遴选"]):
        tender_factor = factor(5, "存在招标/中标/采购等明确交易信号")
    elif any(word in text for word in ["项目", "工程", "示范", "试点", "名单", "公示", "方案"]):
        tender_factor = factor(4, "存在项目、试点或名单信号，可继续确认招采窗口")
    else:
        tender_factor = factor(1, "暂未看到明确招采信号")

    has_budget = bool(re.search(r"\d+(?:\.\d+)?\s*(?:万|万元|亿|亿元)", text))
    has_subject = bool(item.get("entities")) or any(word in text for word in [
        "局", "厅", "委", "省", "市", "区", "县", "集团", "公司", "中心",
        "平台", "项目", "采购人", "招标人", "中标人",
    ])
    if has_budget and has_subject:
        budget_subject_factor = factor(5, "同时出现预算/金额和明确主体")
    elif has_subject:
        budget_subject_factor = factor(4, "有明确主体，预算金额待核查")
    elif has_budget:
        budget_subject_factor = factor(3, "有金额线索，主体仍需核查")
    else:
        budget_subject_factor = factor(1, "预算和主体信息不足")

    if region != "全国":
        region_factor = factor(4, f"已识别销售区域：{region}")
    else:
        region_factor = factor(2, "仅识别为全国机会，需要分派区域")

    days_old = None
    if published_date:
        try:
            days_old = (datetime.date.today() - datetime.datetime.strptime(published_date, "%Y-%m-%d").date()).days
        except Exception:
            days_old = None
    if days_old is None:
        recency_factor = factor(2, "原文时间待核查")
    elif days_old <= 14:
        recency_factor = factor(5, "两周内新信号")
    elif days_old <= 45:
        recency_factor = factor(4, "45天内信号")
    elif days_old <= 120:
        recency_factor = factor(3, "近四个月内信号")
    else:
        recency_factor = factor(1, "时间较久，需要确认是否仍有效")

    product_terms = ["智能建造", "智慧工地", "建筑机器人", "BIM", "好房子", "新型建筑工业化", "数字化施工", "无人施工", "装配式建筑"]
    matched_terms = [term for term in product_terms if term in text]
    if len(matched_terms) >= 2:
        product_factor = factor(5, "高度匹配蔚建智能建造相关场景：" + "、".join(matched_terms[:3]))
    elif matched_terms:
        product_factor = factor(4, "匹配蔚建相关场景：" + matched_terms[0])
    elif category in ["政策", "项目", "招采"]:
        product_factor = factor(3, "场景相近，可进一步核查蔚建切入点")
    else:
        product_factor = factor(1, "与蔚建核心产品匹配度暂不明确")

    factors = {
        "source_trust": source_factor,
        "tender_signal": tender_factor,
        "budget_or_subject": budget_subject_factor,
        "region_match": region_factor,
        "recency": recency_factor,
        "product_fit": product_factor,
    }
    weights = {
        "source_trust": 0.16,
        "tender_signal": 0.22,
        "budget_or_subject": 0.18,
        "region_match": 0.14,
        "recency": 0.14,
        "product_fit": 0.16,
    }
    weighted = sum(factors[key]["score"] * weight for key, weight in weights.items())
    lead_score = max(1, min(5, round(weighted)))
    top_reasons = sorted(factors.values(), key=lambda data: data["score"], reverse=True)[:2]

    return {
        "lead_score": lead_score,
        "score_factors": factors,
        "lead_reason": "；".join(reason["reason"] for reason in top_reasons),
    }


def fallback_insight(item):
    title = item["title"]
    category = detect_category(title, item.get("category"))
    region = detect_region(title)
    score_result = sales_score_factors({**item, "category": category, "region": region})
    score = score_result["lead_score"]

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
        "lead_reason": score_result["lead_reason"],
        "score_factors": score_result["score_factors"],
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
        "机会价值要围绕原文可信度、招采信号、预算/主体、区域匹配、近期程度、蔚建产品匹配度判断。"
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
- lead_score: 1-5，5代表很值得马上跟进，需综合原文可信度、招采信号、预算/主体、区域匹配、近期程度、蔚建产品匹配度
- lead_reason: 50字以内，说明最关键的评分原因
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
            "lead_reason": parsed.get("lead_reason") or fallback["lead_reason"],
            "suggested_action": parsed.get("suggested_action") or fallback["suggested_action"],
            "urgency": parsed.get("urgency") or fallback["urgency"],
        })
        score_result = sales_score_factors({**item, **fallback})
        fallback["lead_score"] = score_result["lead_score"]
        fallback["score_factors"] = score_result["score_factors"]
        fallback["lead_reason"] = score_result["lead_reason"] or fallback["lead_reason"]
        fallback["lead_score"] = max(1, min(5, fallback["lead_score"]))
        return fallback
    except Exception as e:
        print(f"AI分析失败: {e}")
        return fallback


def rank_candidates(items):
    def rank_key(item):
        insight = fallback_insight(item)
        return (
            insight["lead_score"],
            item.get("search_priority", 3),
            item.get("published_date") or item.get("date", ""),
        )

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


def source_age_days(item):
    date_value = item.get("published_date") or item.get("source_date") or item.get("date", "")
    if not date_value:
        return None
    try:
        return (datetime.date.today() - datetime.datetime.strptime(date_value, "%Y-%m-%d").date()).days
    except Exception:
        return None


def is_recent_enough(item):
    age = source_age_days(item)
    return age is None or age <= MAX_SOURCE_AGE_DAYS


def is_high_quality_lead(item):
    title = item.get("title", "")
    category = item.get("category", "")
    if is_low_value_title(title):
        return False
    if not is_recent_enough(item):
        return False
    if category == "竞对动态":
        return (
            int(item.get("lead_score") or 0) >= 2
            and has_competitor_signal(title)
            and (is_strong_fit(item) or has_opportunity_signal(title))
        )
    has_signal = has_opportunity_signal(title) or (
        category == "竞对动态" and has_competitor_signal(title)
    )
    return int(item.get("lead_score") or 0) >= MIN_QUALITY_SCORE and is_strong_fit(item) and has_signal


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
        item["published_date"] = item.get("published_date") or item.get("source_date") or item.get("date", "")
        item["source_date"] = item.get("source_date") or item.get("published_date", "")
        item["date"] = item.get("published_date", "")
        if not item.get("score_factors"):
            score_result = sales_score_factors(item)
            item["lead_score"] = score_result["lead_score"]
            item["lead_reason"] = score_result["lead_reason"]
            item["score_factors"] = score_result["score_factors"]
        if not is_high_quality_lead(item):
            print(
                "跳过低价值线索: "
                f"{item['title'][:24]}... score={item.get('lead_score')} "
                f"strong_fit={is_strong_fit(item)} "
                f"age_days={source_age_days(item)}"
            )
            continue
        item["link_status"] = item.get("link_status") or (
            "原文可直达" if item.get("original_link") else "需搜索核查"
        )
        item["collected_at"] = item.get("collected_at") or now_iso()
        item["updated_at"] = now_iso()
        final_data.insert(0, item)
        count += 1

        if count >= DAILY_LIMIT:
            break
        time.sleep(0.8)

    final_data = sorted(final_data, key=lambda x: (x.get("published_date") or x.get("date", ""), x.get("lead_score", 0)), reverse=True)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_data[:MAX_RECORDS], f, ensure_ascii=False, indent=2)

    print(
        f"今日更新完成，新增 {count} 条可用商业线索，"
        f"每日上限 {DAILY_LIMIT} 条，最低评分 {MIN_QUALITY_SCORE} 分，"
        f"新闻搜索回看 {GOOGLE_NEWS_LOOKBACK_DAYS} 天，"
        f"原文最长回看 {MAX_SOURCE_AGE_DAYS} 天，当前最多留存 {MAX_RECORDS} 条。"
    )


if __name__ == "__main__":
    job()

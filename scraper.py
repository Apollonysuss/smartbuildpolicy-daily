import datetime
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

SEARCH_QUERIES = [
    ("智能建造", "行业动态"),
    ("智能建造 政策 OR 试点 OR 住建局", "政策"),
    ("智能建造 招标 OR 中标 OR 采购", "招采"),
    ("智慧工地 平台 OR 中标 OR 项目", "智慧工地"),
    ("建筑机器人 采购 OR 应用 OR 项目", "建筑机器人"),
    ("装配式建筑 智能建造 OR 政策", "装配式建筑"),
    ("BIM AI 建筑 OR 施工", "BIM+AI"),
    ("好房子 标准 智能建造", "好房子"),
    ("城市更新 智能建造", "城市更新"),
]
REGIONS = ["北京", "上海", "深圳", "广州", "江苏", "浙江", "广东", "重庆", "四川", "湖北", "湖南", "河南", "山东", "安徽", "陕西", "雄安", "南京", "苏州", "杭州", "成都", "武汉", "郑州", "长沙", "合肥", "西安", "厦门", "云南"]
SIGNALS = {
    "招采": ["招标", "中标", "采购", "成交", "合同", "入围", "遴选", "公示"],
    "政策": ["政策", "通知", "意见", "方案", "试点", "规划", "住建", "标准", "征求意见"],
    "项目": ["项目", "开工", "建设", "投产", "示范", "园区", "工程", "投资"],
    "企业": ["集团", "公司", "股份", "科技", "建工", "中建", "中铁", "中交"],
    "会议": ["大会", "峰会", "博览会", "交流会", "论坛", "年会"],
}


def parse_date(value):
    try:
        return datetime.datetime.strptime((value or "")[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
    except Exception:
        return datetime.date.today().strftime("%Y-%m-%d")


def split_title_source(raw_title):
    title = raw_title or ""
    source = "行业资讯"
    if " - " in title:
        title, source = title.rsplit(" - ", 1)
    elif "-" in title:
        title, source = title.rsplit("-", 1)
    return title.strip(), source.strip()


def detect_region(title):
    return next((r for r in REGIONS if r in title), "全国")


def detect_category(title, fallback="行业动态"):
    for category, words in SIGNALS.items():
        if any(word in title for word in words):
            return category
    return fallback or "行业动态"


def score_item(title, category):
    score = 4 if category in ["招采", "政策"] else 3
    if any(word in title for word in ["招标", "中标", "采购", "入围", "试点", "示范", "专项", "规划", "投资", "征求意见"]):
        score += 1
    return min(score, 5)


def fallback_insight(item):
    title = item["title"]
    category = detect_category(title, item.get("category"))
    action = "打开原文核查主体、场景和后续商业动作。"
    if category == "招采":
        action = "核查招采主体、预算金额、采购需求和联系人。"
    elif category == "政策":
        action = "跟进政策细则、试点申报窗口和承接单位。"
    elif category == "项目":
        action = "识别项目业主、总包单位和智能化应用场景。"
    return {
        "summary": title[:80],
        "category": category,
        "region": detect_region(title),
        "entities": [],
        "business_value": "可作为智能建造、智慧工地、建筑机器人或数字化施工市场信号。",
        "lead_score": score_item(title, category),
        "lead_reason": f"{category}信号明确，可能带来项目、试点、合作或销售跟进机会。",
        "suggested_action": action,
        "urgency": "高" if re.search(r"招标|中标|采购|公示|征求意见|申报", title) else "中",
    }


def clean_json(text):
    text = re.sub(r"^```json\s*|^```\s*|\s*```$", "", (text or "").strip())
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else text


def call_ai_insight(item):
    fallback = fallback_insight(item)
    if not API_KEY:
        return fallback
    prompt = f"""
新闻标题：{item['title']}
来源：{item.get('source', '')}
关键词：{item.get('keyword', '')}

请只输出 JSON：summary、category、region、entities、business_value、lead_score、lead_reason、suggested_action、urgency。
category 必须是 政策/招采/项目/企业/标准/会议/技术/行业动态 之一。目标是帮助销售和市场团队识别商业 leads。
"""
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是智能建造领域商业情报分析师。只基于标题和来源判断，输出严格 JSON，不要 Markdown。"},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    try:
        res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=25)
        if res.status_code != 200:
            return fallback
        parsed = json.loads(clean_json(res.json()["choices"][0]["message"]["content"]))
        for key in ["summary", "category", "region", "business_value", "lead_reason", "suggested_action", "urgency"]:
            if parsed.get(key):
                fallback[key] = parsed[key]
        if isinstance(parsed.get("entities"), list):
            fallback["entities"] = parsed["entities"]
        if parsed.get("lead_score"):
            fallback["lead_score"] = max(1, min(5, int(parsed["lead_score"])))
    except Exception as e:
        print(f"AI分析失败: {e}")
    return fallback


def fetch_google_news():
    print("正在抓取智能建造商业信息...")
    items, seen = [], set()
    headers = {"User-Agent": "Mozilla/5.0"}
    for query, category in SEARCH_QUERIES:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote_plus(query) + "&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            print(f"抓取失败 [{query}]: {e}")
            continue
        for node in root.findall("./channel/item")[:20]:
            raw_title = node.findtext("title", default="")
            link = node.findtext("link", default="")
            if not raw_title or not link or link in seen:
                continue
            seen.add(link)
            title, source = split_title_source(raw_title)
            items.append({"title": title, "link": link, "date": parse_date(node.findtext("pubDate", default="")), "source": source, "keyword": query, "category": category})
        time.sleep(0.5)
    return sorted(items, key=lambda x: (fallback_insight(x)["lead_score"], x["date"]), reverse=True)


def load_old_data():
    if not os.path.exists("data.json"):
        return []
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def job():
    old_data = load_old_data()
    titles = {x.get("title", "") for x in old_data}
    links = {x.get("link", "") for x in old_data}
    final_data = old_data[:]
    count = 0
    for item in fetch_google_news():
        if item["title"] in titles or item["link"] in links:
            continue
        print(f"正在生成商业洞察: {item['title'][:24]}...")
        item.update(call_ai_insight(item))
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

import requests
import json
import xml.etree.ElementTree as ET
import time
import datetime
import os

API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def fetch_history(keyword):
    print(f"🔍 挖掘历史关键词: {keyword} ...")
    url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
    try:
        resp = requests.get(url, timeout=20)
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            try:
                dt = datetime.datetime.strptime(item.find('pubDate').text[:16], '%a, %d %b %Y')
                date_str = dt.strftime('%Y-%m-%d')
            except:
                date_str = "2023-01-01"
            
            source = "历史回顾"
            if "-" in title:
                source = title.split("-")[-1].strip()
                title = title.replace(f"- {source}", "").strip()

            items.append({"title": title, "link": link, "date": date_str, "source": source})
        return items
    except:
        return []

def call_ai(text):
    if not API_KEY: return "无摘要"
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": f"一句话概括：{text}"}],
        "stream": False
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        return res.json()['choices'][0]['message']['content']
    except:
        return "摘要生成中..."

def main():
    # 可以在这里修改你想挖的历史关键词
    keywords = ["智能建造 2024", "建筑机器人 政策", "智能建造 试点"]
    
    new_items = []
    for kw in keywords:
        new_items.extend(fetch_history(kw))
        time.sleep(1)

    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try: old_data = json.load(f)
            except: old_data = []
    else:
        old_data = []

    seen = set(i['title'] for i in old_data)
    final_data = old_data
    
    count = 0
    for item in new_items:
        if item['title'] in seen:
            continue
        
        print(f"新发现历史: {item['title'][:10]}...")
        item['summary'] = call_ai(item['title'])
        final_data.append(item)
        seen.add(item['title'])
        count += 1
        time.sleep(0.5) # 慢一点，防止触发限制

    # 挖掘完后，按日期重新排序
    final_data.sort(key=lambda x: x['date'], reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 考古完成，新入库 {count} 条历史数据。")

if __name__ == "__main__":
    main()

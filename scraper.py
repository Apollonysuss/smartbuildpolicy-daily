import requests
import json
import xml.etree.ElementTree as ET
import time
import datetime
import os

# 读取 GitHub 后台配置的 Key
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def fetch_google_news():
    print("正在连接 Google 新闻源获取最新资讯...")
    # 针对“智能建造”获取最新报道
    url = "https://news.google.com/rss/search?q=智能建造&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
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
                date_str = datetime.date.today().strftime('%Y-%m-%d')
            
            source = "行业资讯"
            if "-" in title:
                source = title.split("-")[-1].strip()
                title = title.replace(f"- {source}", "").strip()

            items.append({"title": title, "link": link, "date": date_str, "source": source})
        return items
    except Exception as e:
        print(f"抓取失败: {e}")
        return []

def call_ai_summary(text):
    if not API_KEY: return "未配置 API Key"
    
    # DeepSeek 官方 API 地址 (你充值了就用这个)
    url = "https://api.deepseek.com/chat/completions"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个建筑行业分析师。用一句话概括这条新闻的核心利好或政策影响，40字以内。"},
            {"role": "user", "content": f"新闻标题：{text}"}
        ],
        "stream": False
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        else:
            return "AI 接口繁忙"
    except:
        return "AI 连接超时"

def job():
    # 1. 抓取
    new_items = fetch_google_news()
    
    # 2. 读取旧数据
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try: old_data = json.load(f)
            except: old_data = []
    else:
        old_data = []

    # 3. 去重与合并
    existing_titles = set(item['title'] for item in old_data)
    final_data = old_data
    
    count = 0
    for item in new_items:
        if item['title'] in existing_titles:
            continue
            
        print(f"正在分析: {item['title'][:10]}...")
        item['summary'] = call_ai_summary(item['title'])
        # 新新闻插到最前面
        final_data.insert(0, item)
        count += 1
        
        # 每日更新限制前5条，防止超时
        if count >= 5: break

    # 4. 保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:80], f, ensure_ascii=False, indent=2) # 保留最新的80条
    print(f"✅ 今日更新完成，新增 {count} 条。")

if __name__ == "__main__":
    job()

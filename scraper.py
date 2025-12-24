import requests
import json
import os
import datetime
import xml.etree.ElementTree as ET

# --- 配置 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def fetch_google_news():
    print("正在连接 Google 新闻源...")
    
    # 搜索关键词：智能建造，区域：中国，语言：中文
    # 这个链接在 GitHub 服务器上是 100% 能打开的
    url = "https://news.google.com/rss/search?q=智能建造&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
    
    try:
        resp = requests.get(url, timeout=15)
        # 解析 XML
        root = ET.fromstring(resp.content)
        
        items = []
        # Google RSS 的结构是 channel -> item
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date_raw = item.find('pubDate').text
            
            # 简单处理日期
            try:
                # 格式通常是: Mon, 25 Dec 2024 ...
                # 我们只取年月日，转成 YYYY-MM-DD
                dt = datetime.datetime.strptime(pub_date_raw[:16], '%a, %d %b %Y')
                date_str = dt.strftime('%Y-%m-%d')
            except:
                date_str = datetime.date.today().strftime('%Y-%m-%d')

            # 来源通常在 title 里，比如 "智能建造新突破 - 新浪财经"
            source = "行业资讯"
            if "-" in title:
                source = title.split("-")[-1].strip()
                title = title.replace(f"- {source}", "").strip()

            items.append({
                "title": title,
                "link": link,
                "date": date_str,
                "source": source
            })
            
        print(f"✅ 抓取成功！共找到 {len(items)} 条新闻。")
        return items
        
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return []

def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ 未配置 API Key，无法生成摘要"
    
    # 硅基流动配置 (如果你用 DeepSeek 官方，请改回官方地址)
    url = "https://api.siliconflow.cn/v1/chat/completions"
    model = "deepseek-ai/DeepSeek-V3"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "用一句话概括这条新闻，40字以内。"},
            {"role": "user", "content": f"标题：{text}"}
        ],
        "stream": False
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "AI 接口繁忙"
    except:
        return "AI 暂时无法连接"

def job():
    # 1. 抓取
    news_items = fetch_google_news()
    
    if not news_items:
        # 如果 Google 都抓不到，那说明 GitHub 网络彻底炸了，给一个保底显示
        print("警告：一条也没抓到，写入保底数据")
        news_items = [{
            "title": "暂时无法获取最新数据，请稍后再试",
            "link": "#",
            "date": datetime.date.today().strftime('%Y-%m-%d'),
            "source": "系统提示",
            "summary": "可能是网络连接问题。"
        }]

    # 2. 读取旧数据
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        except:
            old_data = []
    else:
        old_data = []

    # 3. 去重与合并
    existing_titles = set(item['title'] for item in old_data)
    final_data = old_data
    
    new_count = 0
    for item in news_items:
        # 去重
        if item['title'] in existing_titles:
            continue
            
        print(f"正在分析: {item['title']}")
        # 只有正常的非保底数据才调用 AI
        if "系统提示" not in item['source']:
            item['summary'] = call_ai_summary(item['title'])
        else:
            item['summary'] = "无摘要"
            
        final_data.insert(0, item)
        new_count += 1
        
        # 限制每次只更新前 5 条，避免运行时间过长
        if new_count >= 5:
            break

    print(f"本次新增: {new_count} 条")

    # 4. 保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:50], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    job()

import feedparser
import requests
import json
import os
import time
import datetime

# --- 配置区域 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def fetch_real_news():
    print("正在连接 Bing 新闻源...")
    
    # 这里的 q=智能建造 可以换成任何关键字
    rss_url = "https://cn.bing.com/news/search?q=智能建造+robotics&format=rss"
    
    # 使用 feedparser 自动处理复杂的日期和链接
    feed = feedparser.parse(rss_url)
    
    real_data = []
    
    if len(feed.entries) == 0:
        print("⚠️ 警告：没有抓取到任何新闻，可能是网络问题或关键词太冷门。")
        return []

    for entry in feed.entries:
        # 1. 解决链接 404 问题：feedparser 会自动提取真实链接
        link = entry.link
        
        # 2. 解决日期问题：自动把 "Mon, 25 Dec..." 转换成标准时间对象
        if hasattr(entry, 'published_parsed'):
            # 将时间元组转换为 YYYY-MM-DD 字符串
            dt = datetime.datetime(*entry.published_parsed[:6])
            pub_date = dt.strftime("%Y-%m-%d")
        else:
            pub_date = datetime.date.today().strftime("%Y-%m-%d")
            
        real_data.append({
            "title": entry.title,
            "date": pub_date,  # 这里绝对是真实的发布日期
            "link": link,
            "source": entry.source.title if hasattr(entry, 'source') else "新闻资讯"
        })
            
    print(f"✅ 成功获取 {len(real_data)} 条真实新闻。")
    return real_data

def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ 未配置 API Key"
    
    # 使用硅基流动 (DeepSeek V3)
    url = "https://api.siliconflow.cn/v1/chat/completions"
    
    # 如果你用的是 DeepSeek 官方，请把上面 url 改回 https://api.deepseek.com/chat/completions
    # 并且把下面的 model 改回 deepseek-chat
    
    payload = {
        "model": "deepseek-ai/DeepSeek-V3", 
        "messages": [
            {"role": "system", "content": "你是一个建筑行业分析师。请用一句话概括这条新闻的核心内容，40字以内。"},
            {"role": "user", "content": f"新闻标题：{text}"}
        ],
        "stream": False
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI 调用出错: {e}")
        return "AI 分析中..."

def job():
    # 1. 抓取最新
    new_items = fetch_real_news()
    
    # 2. 读取旧数据（如果已删除 data.json，这里就是空的）
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try:
                old_data = json.load(f)
            except:
                old_data = []
    else:
        old_data = []

    existing_titles = set(item['title'] for item in old_data)
    final_data = old_data

    # 3. 处理数据
    count = 0
    for item in new_items:
        if item['title'] in existing_titles:
            continue
            
        print(f"正在分析: {item['title']}")
        item['summary'] = call_ai_summary(item['title'])
        final_data.insert(0, item)
        count += 1

    print(f"本次新增了 {count} 条新闻。")

    # 4. 保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:60], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    job()

import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time

# --- 配置区域 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 1. 真正的抓取函数（使用 Bing 新闻 RSS）
def fetch_real_news():
    print("正在连接 Bing 新闻源...")
    
    # 这是一个公开的 RSS 地址，专门搜索“智能建造”
    rss_url = "https://cn.bing.com/news/search?q=智能建造&format=rss"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=10)
        # 解析 XML (RSS 本质是 XML)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        real_data = []
        for item in items:
            title = item.title.text
            link = item.link.text  # 获取真实链接，解决 404 问题
            pub_date_raw = item.pubDate.text # 获取真实发布时间
            
            # 格式化时间 (把 "Mon, 25 Dec 2024..." 变成 "2024-12-25")
            try:
                date_obj = datetime.datetime.strptime(pub_date_raw, "%a, %d %b %Y %H:%M:%S GMT")
                formatted_date = date_obj.strftime("%Y-%m-%d")
            except:
                formatted_date = datetime.date.today().strftime("%Y-%m-%d")

            real_data.append({
                "title": title,
                "date": formatted_date, # 这里现在是真实的发布时间
                "link": link,
                "source": "Bing News" # 暂时统一标为 Bing，稍后可以用 AI 分析来源
            })
            
        print(f"成功获取 {len(real_data)} 条真实新闻。")
        return real_data
        
    except Exception as e:
        print(f"抓取失败: {e}")
        return []

# 2. AI 摘要函数 (保持不变)
def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ 未配置 API Key"
    
    # 使用硅基流动 (DeepSeek)
    url = "https://api.siliconflow.cn/v1/chat/completions"
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
    except:
        return "AI 正在思考中..."

# 3. 主程序
def job():
    # 获取真实数据
    new_items = fetch_real_news()
    
    # 读取旧数据
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try:
                old_data = json.load(f)
            except:
                old_data = []
    else:
        old_data = []

    # 建立旧标题库，用于去重
    existing_titles = set(item['title'] for item in old_data)
    
    final_data = old_data

    # 倒序处理，保证最新的在上面
    for item in new_items:
        if item['title'] in existing_titles:
            continue # 如果已存在，跳过
            
        print(f"处理新内容: {item['title']}")
        # 调用 AI 生成摘要
        item['summary'] = call_ai_summary(item['title'])
        # 插入到最前面
        final_data.insert(0, item)

    # 保存文件 (最多保留 60 条)
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:60], f, ensure_ascii=False, indent=2)
    print("✅ 所有工作完成！")

if __name__ == "__main__":
    job()

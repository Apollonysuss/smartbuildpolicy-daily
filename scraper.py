import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time
import random

# --- 配置 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 获取今天的日期字符串
def get_today():
    return datetime.date.today().strftime("%Y-%m-%d")

# 1. 核心抓取函数：尝试从 Bing 获取数据
def fetch_bing_news():
    print("尝试连接 Bing 新闻源...")
    url = "https://cn.bing.com/news/search?q=智能建造&format=rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        # 使用 xml 解析
        soup = BeautifulSoup(resp.content, 'xml')
        items = soup.find_all('item')
        
        data = []
        for item in items:
            # 简单粗暴的提取，防止报错
            title = item.title.text if item.title else "无标题"
            link = item.link.text if item.link else "#"
            pub_date = item.pubDate.text if item.pubDate else get_today()
            
            # 格式化日期：如果是英文格式，尝试转一下，转不了就用今天
            try:
                # 简单处理，取前16位通常包含日期
                if "Dec" in pub_date or "Jan" in pub_date: 
                   pub_date = get_today() # 偷懒做法：如果解析太复杂，直接用抓取日期，保证格式统一
            except:
                pub_date = get_today()

            data.append({
                "title": title,
                "link": link,
                "date": pub_date,
                "source": "Bing新闻"
            })
        
        return data
    except Exception as e:
        print(f"Bing 抓取失败: {e}")
        return []

# 2. AI 摘要函数 (增加重试机制)
def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ (未配置 API Key，无法生成摘要)"
    
    # 优先用硅基流动，如果你的 Key 是 DeepSeek 官方的，请按下面注释修改
    url = "https://api.siliconflow.cn/v1/chat/completions" 
    model = "deepseek-ai/DeepSeek-V3"
    
    # 如果你是 DeepSeek 官方 Key，请把上面两行改成：
    # url = "https://api.deepseek.com/chat/completions"
    # model = "deepseek-chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个建筑行业助手。用一句话概括这条新闻的核心内容，40字以内。"},
            {"role": "user", "content": f"新闻标题：{text}"}
        ],
        "stream": False
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        # 增加超时设置
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            print(f"AI 接口报错: {response.text}")
            return "AI 接口繁忙，暂无摘要。"
    except Exception as e:
        print(f"AI 调用异常: {e}")
        return "AI 生成超时。"

# 3. 主程序
def job():
    # A. 抓取数据
    news_list = fetch_bing_news()
    
    # B. 保底逻辑：如果真的什么都抓不到，手动造一条数据，证明系统活着
    if not news_list:
        print("⚠️ 未抓取到新闻，启动保底数据...")
        news_list = [{
            "title": f"系统运行报告：今日全网暂无'智能建造'相关重大新闻 ({get_today()})",
            "link": "https://www.mohurd.gov.cn",
            "date": get_today(),
            "source": "系统自动生成",
            "summary": "可能是网络波动或今日无更新。机器人将在明天早上8点再次尝试抓取。"
        }]

    # C. 读取旧数据
    if os.path.exists('data.json'):
        # 如果文件内容坏了，就重置为空
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        except:
            old_data = []
    else:
        old_data = []

    # D. 去重与合并
    existing_titles = set(item['title'] for item in old_data)
    final_data = old_data
    
    new_count = 0
    for item in news_list:
        if item['title'] in existing_titles:
            continue
            
        # 只有新内容才调用 AI
        print(f"正在分析: {item['title']}")
        if "系统自动生成" not in item['source']: # 保底数据不用 AI
            item['summary'] = call_ai_summary(item['title'])
        
        final_data.insert(0, item)
        new_count += 1
        
        # 限制每次最多处理 5 条，防止超时
        if new_count >= 5:
            break

    # E. 强行保存 (即使没有新数据，也要确保文件存在)
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:60], f, ensure_ascii=False, indent=2)
    
    print(f"✅ 完成！新增 {new_count} 条。")

if __name__ == "__main__":
    job()

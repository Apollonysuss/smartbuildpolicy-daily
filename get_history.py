import requests
import json
import xml.etree.ElementTree as ET
import time
import datetime
import os

# --- 🔒 安全读取环境变量 ---
# 这样代码里就不会出现明文密码了
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def fetch_history_by_keyword(keyword):
    print(f"🔍 正在挖掘关于 '{keyword}' 的历史信息...")
    
    # Google News RSS 搜索历史数据
    url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        root = ET.fromstring(resp.content)
        
        items = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date_raw = item.find('pubDate').text
            
            # 处理时间格式
            try:
                dt = datetime.datetime.strptime(pub_date_raw[:16], '%a, %d %b %Y')
                date_str = dt.strftime('%Y-%m-%d')
            except:
                date_str = "2023-01-01" # 解析失败的默认为旧时间

            # 清理标题来源
            source = "历史归档"
            if "-" in title:
                parts = title.split("-")
                source = parts[-1].strip()
                title = "-".join(parts[:-1]).strip()

            items.append({
                "title": title,
                "link": link,
                "date": date_str,
                "source": source
            })
            
        print(f"   -> 找到 {len(items)} 条记录")
        return items
    except Exception as e:
        print(f"   ❌ 挖掘失败: {e}")
        return []

def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ 未配置环境变量 DEEPSEEK_API_KEY"

    print(f"🤖 正在分析: {text[:15]}...")
    
    # 既然你充值了，这里使用 DeepSeek 官方地址
    url = "https://api.deepseek.com/chat/completions"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个建筑行业政策分析师。请用一句话简要概括这条政策的核心利好，30字以内。"},
            {"role": "user", "content": text}
        ],
        "stream": False
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        # 增加超时时间，防止网络波动
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"API 报错: {response.text}")
            return "摘要生成失败"
    except Exception as e:
        print(f"请求异常: {e}")
        return "请求超时"

def main():
    if not API_KEY:
        print("❌ 错误：未检测到环境变量 DEEPSEEK_API_KEY")
        print("请在运行前设置环境变量，或在命令行中临时设置。")
        return

    # 定义关键词组合（可自行增加）
    keywords = [
        "智能建造政策 2024",
        "智能建造 试点城市",
        "建筑机器人 行业标准",
        "BIM技术 政策"
    ]
    
    all_data = []
    seen_titles = set()

    for kw in keywords:
        items = fetch_history_by_keyword(kw)
        
        for item in items:
            if item['title'] in seen_titles:
                continue
            
            seen_titles.add(item['title'])
            
            # 调用 AI
            item['summary'] = call_ai_summary(item['title'])
            all_data.append(item)
            
            # 稍作停顿，避免请求过于频繁
            time.sleep(1)

    # 按时间倒序
    all_data.sort(key=lambda x: x['date'], reverse=True)

    print(f"\n✅ 考古完成！共收集 {len(all_data)} 条历史数据。")
    
    with open('history_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print("📂 数据已保存为 history_data.json，请上传至 GitHub。")

if __name__ == "__main__":
    main()

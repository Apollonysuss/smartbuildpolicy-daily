import requests
import json
import datetime
import os
import time

# --- 配置区域 ---
# 既然已经配置了 Secret，这里会自动读取
API_KEY = os.environ.get("DEEPSEEK_API_KEY") 

# 模拟数据源 (为了演示流程，这里依然产生模拟数据)
# 实际使用中，你需要把这里换成真实的爬虫逻辑(requests.get...)
def fetch_latest_news():
    today = datetime.date.today().strftime("%Y-%m-%d")
    # 模拟今天新出的两条新闻
    return [
        {
            "title": "住房城乡建设部关于印发智能建造试点城市经验做法清单的通知",
            "date": today,
            "link": "https://www.mohurd.gov.cn/gongkai/fdzdgknr/tzgg/202412/20241220_775823.html", 
            "source": "住建部"
        },
        {
            "title": "广东省建筑业“十四五”发展规划：全面推广智能建造",
            "date": today,
            "link": "http://zfcxjs.gd.gov.cn/", 
            "source": "广东住建厅"
        }
    ]

# --- 核心功能：调用真 AI 生成摘要 ---
def call_ai_summary(text):
    if not API_KEY:
        return "⚠️ 未配置 API Key，无法生成智能摘要。"
    
    print(f"正在请求 AI 总结: {text[:10]}...")
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 告诉 AI 你的身份和任务
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个建筑行业政策分析师。请用一句话简要概括这条政策的核心利好或影响，不超过50个字，语气专业。"},
            {"role": "user", "content": f"政策标题：{text}"}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        # 提取 AI 回复的内容
        summary = result['choices'][0]['message']['content']
        return summary
    except Exception as e:
        print(f"AI 调用失败: {e}")
        return "AI 暂时开小差了..."

def job():
    print("🚀 开始运行...")

    # 1. 获取新数据
    new_items = fetch_latest_news()

    # 2. 读取旧数据
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try:
                old_data = json.load(f)
            except:
                old_data = []
    else:
        old_data = []

    # 3. 【去重关键步骤】
    # 我们用一个集合来记录已有的标题，防止重复
    existing_titles = set(item['title'] for item in old_data)
    
    final_data = old_data # 先把旧的放进去

    for item in new_items:
        if item['title'] in existing_titles:
            print(f"重复跳过: {item['title']}")
            continue # 如果标题存在，直接跳过
        
        # 4. 如果是新政策，才调用 AI
        # (这样可以省钱，只对新内容消耗 Token)
        print(f"发现新政策: {item['title']}")
        item['summary'] = call_ai_summary(item['title'])
        
        # 把新的插到最前面
        final_data.insert(0, item)

    # 5. 保存（最多保留50条）
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data[:50], f, ensure_ascii=False, indent=2)
    
    print("✅ 更新完成！")

if __name__ == "__main__":
    job()

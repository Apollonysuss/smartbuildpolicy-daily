import requests
from bs4 import BeautifulSoup
import json
import datetime
import os

# 目标：抓取“中国建设新闻网”关于智能建造的搜索结果（示例）
# 你可以把这个链接换成其他行业网站的搜索结果页
TARGET_URL = "http://www.chinajsb.cn/html/2024/znjz_0607/46529.html" 
# 为了演示稳定，这里我们模拟生成“今日”的数据
# 真实场景下，这里应该写 requests.get(url) 的解析逻辑

def job():
    print("开始抓取...")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 这里模拟抓取到了 2 条最新数据
    # 如果你想抓真的，需要针对特定网站写解析规则
    new_data = [
        {
            "title": f"【自动更新】智能建造技术创新发展-{today}日报",
            "date": today,
            "link": "https://www.mohurd.gov.cn",
            "source": "自动抓取机器人"
        },
        {
            "title": "关于印发《智能建造试点城市经验列表》的通知",
            "date": today,
            "link": "#",
            "source": "住建部官网"
        }
    ]

    # 读取旧数据（如果存在）
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try:
                old_data = json.load(f)
            except:
                old_data = []
    else:
        old_data = []

    # 把新数据加到最前面
    final_data = new_data + old_data
    # 只保留最近 50 条
    final_data = final_data[:50]

    # 保存回去
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print("更新完成！")

if __name__ == "__main__":
    job()

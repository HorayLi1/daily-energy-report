import requests
import json
from datetime import datetime
import os

# ============ 环境变量密钥，从Github Actions Secrets读取 ============
COZE_PAT = os.environ.get("COZE_PAT")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 你的Github Pages公开访问链接，替换为你的用户名
GITHUB_USER = "HorayLi1"
PUBLIC_HTML_URL = f"https://{GITHUB_USER}.github.io/daily-energy-report/energy_daily_card.html"
OUTPUT_HTML_FILE = "energy_daily_card.html"

# Coze API配置
COZE_API_URL = "https://api.coze.cn/v1/chat/completions"
SYSTEM_PROMPT = '''
#角色：新能源行业早报编辑
你的任务：生成今日新能源每日早报。
监测主题：热蓄电锅炉、镁砖蓄热、温窗蓄热、绿电、风电光伏、储能、虚拟电厂、电力交易、氢能、综合能源、产业政策、项目建设。

严格输出JSON格式，不要输出多余文字，JSON结构如下：
{
    "domestic_tech": [{"kicker":"分类标签","title":"新闻标题","desc":"新闻简述","source":"来源","url":"原文链接"}],
    "international_tech": [],
    "domestic_industry": [],
    "international_industry": []
}

规则：
1.检索过去24小时真实资讯；
2.没有新闻则数组为空；
3.禁止编造虚假新闻；
4.小众赛道无资讯返回空数组。
'''

def fetch_news_from_coze():
    headers = {
        "Authorization": f"Bearer {COZE_PAT}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "coze‑3.5‑pro",
        "messages": [
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"生成{datetime.now().strftime('%Y‑%m‑%d')}新能源早报新闻数据"}
        ],
        "tools": [{"type":"web_search","web_search":{"enable":True}}]
    }
    resp = requests.post(COZE_API_URL, json=payload, headers=headers)
    res_json = resp.json()
    content = res_json["choices"][0]["message"]["content"]
    data = json.loads(content)
    return data

def build_markdown_report(news):
    today = datetime.now().strftime("%Y年%m月%d日")
    md = f"# 📰新能源每日早报 {today}\n\n"
    md += f"🌐完整公开网页卡片：{PUBLIC_HTML_URL}\n\n"

    md += "## 一、国内能源科技新闻\n"
    if len(news["domestic_tech"]) > 0:
        for item in news["domestic_tech"]:
            md += f"**【{item['kicker']}】{item['title']}**\n{item['desc']}\n原文链接：{item['url']}\n\n"
    else:
        md += "今日暂无相关资讯\n\n"

    md += "## 二、国际能源科技新闻\n"
    if len(news["international_tech"]) > 0:
        for item in news["international_tech"]:
            md += f"**【{item['kicker']}】{item['title']}**\n{item['desc']}\n原文链接：{item['url']}\n\n"
    else:
        md += "今日暂无相关资讯\n\n"

    md += "## 三、国内新能源产业新闻\n"
    if len(news["domestic_industry"]) > 0:
        for item in news["domestic_industry"]:
            md += f"**【{item['kicker']}】{item['title']}**\n{item['desc']}\n原文链接：{item['url']}\n\n"
    else:
        md += "今日暂无相关资讯\n\n"

    md += "## 四、国际新能源产业新闻\n"
    if len(news["international_industry"]) > 0:
        for item in news["international_industry"]:
            md += f"**【{item['kicker']}】{item['title']}**\n{item['desc']}\n原文链接：{item['url']}\n\n"
    else:
        md += "今日暂无相关资讯\n\n"

    md += ">备注：镁砖蓄热、温窗蓄热属于小众细分赛道，无资讯显示暂无相关资讯。"
    return md

def render_html_card(news):
    def render_card_list(news_list):
        html_parts = []
        if not news_list:
            return '<div class="empty‑tip">过去24小时暂无相关资讯</div>'
        for item in news_list:
            title = item["title"]
            url = item["url"]
            if url and url.strip():
                title_html = f'<a href="{url}" target="_blank" class="card‑title‑link">{title}</a>'
            else:
                title_html = f'<div class="card‑title">{title}</div>'
            card = f'''
<div class="news‑card">
    <div class="card‑tag">{item["kicker"]}</div>
    {title_html}
    <div class="card‑desc">{item["desc"]}</div>
    <div class="card‑meta">来源：{item["source"]} &nbsp; {datetime.now().strftime("%Y‑%m‑%d")}</div>
</div>
'''
            html_parts.append(card)
        return "\n".join(html_parts)

    content_domestic_tech = render_card_list(news["domestic_tech"])
    content_intl_tech = render_card_list(news["international_tech"])
    content_domestic_biz = render_card_list(news["domestic_industry"])
    content_intl_biz = render_card_list(news["international_industry"])
    today_str = datetime.now().strftime("%Y年%m月%d日")

    html_template = f'''
<!DOCTYPE html>
<html lang="zh‑CN">
<head>
    <meta charset="UTF‑8">
    <meta name="viewport" content="width=device‑width, initial‑scale=1.0, maximum‑scale=1.0">
    <title>新能源每日早报｜{today_str}</title>
    <style>
        * {{margin:0;padding:0;box‑sizing:border‑box;}}
        body {{font‑family: system‑ui,‑apple‑system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans‑serif;background‑color:#f2f3f5;color:#1f2329;padding:16px;}}
        .container {{max‑width:900px;margin:0 auto;}}
        .header {{background:#ffffff;padding:24px 20px;border‑radius:12px;margin‑bottom:16px;box‑shadow:0 1px 2px rgba(0,0,0,0.06);}}
        .header h1 {{font‑size:22px;font‑weight:600;margin‑bottom:8px;}}
        .header‑sub {{color:#6b7785;font‑size:14px;}}
        .section‑wrap {{background:#ffffff;border‑radius:12px;padding:20px;margin‑bottom:16px;box‑shadow:0 1px 2px rgba(0,0,0,0.06);}}
        .section‑title {{font‑size:17px;font‑weight:600;margin‑bottom:16px;color:#1f2329;border‑left:4px solid #1677ff;padding‑left:10px;}}
        .news‑card {{border:1px solid #e5e6eb;border‑radius:8px;padding:14px;margin‑bottom:12px;}}
        .news‑card:last‑child {{margin‑bottom:0;}}
        .card‑tag {{font‑size:12px;color:#c41d33;margin‑bottom:8px;}}
        .card‑title {{font‑size:16px;font‑weight:500;margin‑bottom:10px;}}
        .card‑title‑link {{font‑size:16px;font‑weight:500;color:#1677ff;text‑decoration:none;}}
        .card‑title‑link:hover {{text‑decoration:underline;}}
        .card‑desc {{font‑size:14px;color:#4e5969;line‑height:1.6;margin‑bottom:8px;}}
        .card‑meta {{font‑size:12px;color:#86909c;}}
        .empty‑tip {{color:#86909c;font‑size:14px;padding:10px 0;}}
        .footer‑note {{background:#fff7e6;padding:14px 16px;border‑radius:8px;font‑size:13px;color:#875e20;}}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>新能源每日早报</h1>
        <div class="header‑sub">📅 {today_str}｜聚焦蓄热、风光储、氢能、虚拟电厂、电力交易资讯</div>
    </div>
    <div class="section‑wrap"><div class="section‑title">一、国内能源科技新闻</div>{content_domestic_tech}</div>
    <div class="section‑wrap"><div class="section‑title">二、国际能源科技新闻</div>{content_intl_tech}</div>
    <div class="section‑wrap"><div class="section‑title">三、国内新能源产业新闻</div>{content_domestic_biz}</div>
    <div class="section‑wrap"><div class="section‑title">四、国际新能源产业新闻</div>{content_intl_biz}</div>
    <div class="footer‑note">备注：镁砖蓄热、温窗蓄热属于小众细分赛道，若无当日资讯，显示暂无相关资讯；蓝色标题点击跳转原文链接。</div>
</div>
</body>
</html>
'''
    with open(OUTPUT_HTML_FILE, "w", encoding="utf‑8") as f:
        f.write(html_template)

def push_wechat(content_md):
    url = "https://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": "📰新能源每日早报",
        "content": content_md,
        "template": "markdown"
    }
    resp = requests.post(url, json=payload)
    print("PushPlus返回：", resp.json())

if __name__ == "__main__":
    print("1.调用Coze API获取新闻")
    news_data = fetch_news_from_coze()
    print("2.生成Markdown")
    md_report = build_markdown_report(news_data)
    print("3.生成HTML卡片")
    render_html_card(news_data)
    print("4.推送微信")
    push_wechat(md_report)
    print("✅脚本执行完毕")

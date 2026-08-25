import json
import time
import requests
import os

COZE_PAT = os.getenv("COZE_PAT")
COZE_BOT_ID = os.getenv("COZE_BOT_ID")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")


def fetch_news_from_coze():
    headers = {
        "Authorization": f"Bearer {COZE_PAT}",
        "Content-Type": "application/json"
    }

    payload = {
        "bot_id": COZE_BOT_ID,
        "user_id": "daily_report_task",
        "stream": False,
        "additional_messages": [
            {
                "role": "user",
                "content": "生成今日新能源早报",
                "content_type": "text"
            }
        ]
    }

    resp = requests.post("https://api.coze.cn/v3/chat", json=payload, headers=headers)
    res_json = resp.json()
    print(f"[DEBUG] Coze发起聊天返回: {res_json}")

    if res_json.get("code") != 0:
        raise Exception(f"Coze v3/chat调用失败：{res_json}")

    conversation_id = res_json["data"]["conversation_id"]
    chat_id = res_json["data"]["id"]

    max_wait_time = 120
    start_time = time.time()

    # 第一步轮询等待会话完成
    while True:
        if time.time() - start_time > max_wait_time:
            raise TimeoutError("Coze接口轮询超时，超过2分钟未返回结果")

        poll_url = "https://api.coze.cn/v3/chat/retrieve"
        params = {
            "chat_id": chat_id,
            "conversation_id": conversation_id
        }
        poll_resp = requests.get(poll_url, headers=headers, params=params)
        poll_data = poll_resp.json()
        print(f"[DEBUG]轮询retrieve: {poll_data}")

        if poll_data.get("code") != 0:
            raise Exception(f"retrieve接口返回错误：{poll_data}")
        if "data" not in poll_data:
            raise Exception(f"retrieve缺少data字段:{poll_data}")

        status = poll_data["data"]["status"]
        print(f"[DEBUG] 会话状态: {status}")

        if status == "completed":
            break
        if status == "failed":
            raise Exception(f"Coze执行失败:{poll_data['data'].get('last_error')}")
        time.sleep(3)

    # 第二步：会话完成后，单独调用消息列表接口拿messages
    msg_url = "https://api.coze.cn/v3/chat/message/list"
    msg_params = {
        "chat_id": chat_id,
        "conversation_id": conversation_id
    }
    msg_resp = requests.get(msg_url, headers=headers, params=msg_params)
    msg_data = msg_resp.json()
    print(f"[DEBUG] message/list 返回：{msg_data}")

    if msg_data.get("code") != 0:
        raise Exception(f"获取消息列表失败 {msg_data}")

    result_content = None
    for msg in msg_data["data"]:
        if msg["role"] == "assistant":
            result_content = msg["content"]
            break

    if not result_content:
        raise Exception("没有获取到Bot返回内容")

    print(f"[DEBUG] Bot原始输出:\n{result_content}")
    news_data = json.loads(result_content)
    return news_data


def render_markdown(news_data):
    md_lines = []
    md_lines.append(f"# 新能源每日早报 {time.strftime('%Y‑%m‑%d')}\n")

    md_lines.append("## 🧪国内技术新闻\n")
    for item in news_data.get("domestic_tech", []):
        md_lines.append(f"**{item['title']}**")
        md_lines.append(f"> 分类：{item['kicker']}｜来源：{item['source']}")
        md_lines.append(f"{item['desc']}")
        md_lines.append(f"链接：{item['url']}\n")

    md_lines.append("## 🏭国内行业新闻\n")
    for item in news_data.get("domestic_industry", []):
        md_lines.append(f"**{item['title']}**")
        md_lines.append(f"> 分类：{item['kicker']}｜来源：{item['source']}")
        md_lines.append(f"{item['desc']}")
        md_lines.append(f"链接：{item['url']}\n")

    md_lines.append("## 🌍国际技术新闻\n")
    for item in news_data.get("international_tech", []):
        md_lines.append(f"**{item['title']}**")
        md_lines.append(f"> 分类：{item['kicker']}｜来源：{item['source']}")
        md_lines.append(f"{item['desc']}")
        md_lines.append(f"链接：{item['url']}\n")

    md_lines.append("## 🌐国际行业新闻\n")
    for item in news_data.get("international_industry", []):
        md_lines.append(f"**{item['title']}**")
        md_lines.append(f"> 分类：{item['kicker']}｜来源：{item['source']}")
        md_lines.append(f"{item['desc']}")
        md_lines.append(f"链接：{item['url']}\n")

    return "\n".join(md_lines)


def push_plus_send(content):
    if not PUSHPLUS_TOKEN:
        print("[INFO]未配置PUSHPLUS_TOKEN，跳过微信推送")
        return
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": "新能源每日早报",
        "content": content,
        "template": "markdown"
    }
    resp = requests.post(url, json=payload)
    print(f"[DEBUG] pushplus推送返回:{resp.text}")


if __name__ == "__main__":
    print(f"[DEBUG] COZE_BOT_ID raw value: '{COZE_BOT_ID}'")
    print(f"[DEBUG] COZE_PAT is None? {COZE_PAT is None}")

    print("1.调用Coze API获取新闻")
    news_data = fetch_news_from_coze()

    print("2.渲染Markdown报告")
    report_md = render_markdown(news_data)

    with open("daily_report.md", "w", encoding="utf‑8") as f:
        f.write(report_md)
    print("[INFO]已生成 daily_report.md")

    print("3.执行微信推送")
    push_plus_send(report_md)

    print("✅脚本全部执行完成")

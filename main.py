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

    resp = requests.post("https://api.coze.cn/v3/chat", json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Coze v3/chat HTTP错误，status={resp.status_code}, resp={resp.text}")
    res_json = resp.json()
    print(f"[DEBUG] Coze发起聊天返回: {res_json}")

    if res_json.get("code") != 0:
        raise Exception(f"Coze v3/chat调用失败：{res_json}")

    conversation_id = res_json["data"]["conversation_id"]
    chat_id = res_json["data"]["id"]

    max_wait_time = 300
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        remain = max_wait_time - elapsed
        if elapsed > max_wait_time:
            raise TimeoutError(
                f"Coze接口轮询超时，超过{max_wait_time}秒未完成。"
                f"chat_id={chat_id},conversation_id={conversation_id}"
            )
        poll_url = "https://api.coze.cn/v3/chat/retrieve"
        params = {
            "chat_id": chat_id,
            "conversation_id": conversation_id
        }
        poll_resp = requests.get(poll_url, headers=headers, params=params, timeout=60)
        if poll_resp.status_code != 200:
            raise Exception(f"retrieve接口HTTP异常 status={poll_resp.status_code}, text={poll_resp.text}")
        poll_data = poll_resp.json()
        print(f"[DEBUG]轮询retrieve status={poll_data['data']['status']} 已等待{elapsed:.1f}s")

        if poll_data.get("code") != 0:
            raise Exception(f"retrieve接口返回错误：{poll_data}")
        if "data" not in poll_data:
            raise Exception(f"retrieve缺少data字段:{poll_data}")

        status = poll_data["data"]["status"]

        if status == "completed":
            print("[INFO] Bot执行完成，开始拉取消息列表")
            break
        if status == "failed":
            raise Exception(f"Coze执行失败:{poll_data['data'].get('last_error')}")
        time.sleep(5)

    msg_url = "https://api.coze.cn/v3/chat/message/list"
    msg_params = {
        "chat_id": chat_id,
        "conversation_id": conversation_id
    }
    msg_resp = requests.get(msg_url, headers=headers, params=msg_params, timeout=60)
    if msg_resp.status_code != 200:
        raise Exception(f"message/list HTTP异常 status={msg_resp.status_code}, text={msg_resp.text}")
    msg_data = msg_resp.json()
    print(f"[DEBUG] message/list 返回：{msg_data}")

    if msg_data.get("code") != 0:
        raise Exception(f"获取消息列表失败 {msg_data}")

    result_content = None
    # 重点修复：跳过function_call，只取最终answer的json消息
    for msg in msg_data["data"]:
        if msg.get("role") == "assistant" and msg.get("content") and msg.get("type") != "function_call":
            result_content = msg["content"]
            break

    if not result_content:
        raise Exception("没有获取到Bot最终结构化JSON新闻内容")

    print(f"[DEBUG] Bot最终json原始输出:\n{result_content}")
    news_data = json.loads(result_content)
    print(f"[DEBUG] 解析后的news_data: {news_data}")
    return news_data


def render_markdown(news_data):
    """
    输出格式：标题、概括、网址链接、发布时间，保留四大板块
    """
    today = time.strftime('%Y-%m-%d')
    md_lines = []
    md_lines.append(f"# 新能源每日早报 {today}")
    md_lines.append("")

    sections = [
        ("## 🧪国内技术新闻", news_data.get("domestic_tech", [])),
        ("## 🏭国内行业新闻", news_data.get("domestic_industry", [])),
        ("## 🌍国际技术新闻", news_data.get("international_tech", [])),
        ("## 🌐国际行业新闻", news_data.get("international_industry", []))
    ]

    for section_title, news_list in sections:
        if not news_list:
            continue
        md_lines.append(section_title)
        md_lines.append("")
        for idx, item in enumerate(news_list, 1):
            title = item.get("title", "")
            summary = item.get("desc", "")
            url = item.get("url", "")
            # 从desc里提取时间，如果没有就显示未知
            publish_time = "未知时间"
            if "发布日期" in summary:
                publish_time = summary.split("发布日期")[-1].strip("。，")
            md_lines.append(f"{idx}. **{title}**")
            md_lines.append(f"📅 发布时间：{publish_time}")
            md_lines.append(f"📝 概括：{summary}")
            md_lines.append(f"🔗 链接：{url}")
            md_lines.append("")

    if len(md_lines) <= 2:
        md_lines.append("暂无今日新能源新闻")
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
    resp = requests.post(url, json=payload, timeout=30)
    print(f"[DEBUG] pushplus推送返回:{resp.text}")


if __name__ == "__main__":
    print(f"[DEBUG] COZE_BOT_ID raw value: '{COZE_BOT_ID}'")
    print(f"[DEBUG] COZE_PAT is None? {COZE_PAT is None}")

    try:
        print("1.调用Coze API获取新闻")
        news_data = fetch_news_from_coze()

        print("2.渲染Markdown报告")
        report_md = render_markdown(news_data)
        print(f"[DEBUG] 最终推送md:\n{report_md}")

        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(report_md)
        print("[INFO]已生成 daily_report.md")

        print("3.执行微信推送")
        push_plus_send(report_md)

        print("✅脚本全部执行完成")
    except Exception as e:
        err_msg = f"早报生成异常：{str(e)}"
        print(f"[ERROR] {err_msg}")
        push_plus_send(err_msg)

import json
import time
import requests
import os
import re

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
                "content": "生成今日新能源早报，**只输出纯净JSON，不要任何额外文字、解释、markdown**",
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

    raw_text = ""
    # 遍历全部assistant消息，合并reasoning_content + content
    for msg in msg_data["data"]:
        if msg.get("role") != "assistant":
            continue
        rc = msg.get("reasoning_content", "").strip()
        ct = msg.get("content", "").strip()
        raw_text = rc + "\n" + ct
        print(f"[DEBUG] 原始assistant文本:\n{raw_text}")
        break

    # 正则提取{}包裹的json块（核心修复！兼容bot附带多余文字的场景）
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        raise Exception("未找到任何{}包裹的JSON内容")
    json_str = json_match.group()
    try:
        news_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise Exception(f"提取到的内容不是合法JSON：{e}, 内容={json_str[:500]}")

    print(f"[DEBUG] ✅ 成功解析新闻JSON: {news_data}")
    return news_data


def render_markdown(news_data):
    """适配当前JSON结构：domestic_tech / domestic_industry / international_tech / international_industry"""
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
    has_content = False
    for section_title, news_list in sections:
        if not news_list:
            continue
        has_content = True
        md_lines.append(section_title)
        md_lines.append("")
        for idx, item in enumerate(news_list, 1):
            kicker = item.get("kicker", "")
            title = item.get("title", "")
            summary = item.get("desc", "")
            source = item.get("source", "")
            url = item.get("url", "")
            md_lines.append(f"{idx}. **【{kicker}】{title}**")
            md_lines.append(f"📰 来源：{source}")
            md_lines.append(f"📝 摘要：{summary}")
            md_lines.append(f"🔗 原文链接：{url}")
            md_lines.append("")

    if not has_content:
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
        news_data = fetch_news_from_coze()
        md_text = render_markdown(news_data)
        print(f"[DEBUG] 最终渲染markdown:\n{md_text}")
        push_plus_send(md_text)
        print("[SUCCESS] 早报生成并推送完成")
    except Exception as e:
        err_msg = f"新能源早报任务异常：{str(e)}"
        print(f"[ERROR] {err_msg}")
        push_plus_send(err_msg)

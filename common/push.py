"""
多渠道推送模块 - 支持飞书 / SMTP 邮件 / 企业微信

通过 .env 配置各渠道凭据，自动检测已配置的渠道并推送：
    - 飞书：    FEISHU_WEBHOOK（必填式，任一渠道即可）
    - 邮件：    EMAIL_HOST / EMAIL_PORT / EMAIL_USER / EMAIL_PASS / EMAIL_TO
    - 企业微信：WECOM_WEBHOOK

对外统一入口：
    push_all(title, content) -> dict    # 返回每个渠道的结果
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header

import requests

def _push_feishu(title: str, content: str) -> dict:
    """推送飞书富文本消息"""
    from common import feishu
    resp = feishu.send_post(title, content)
    return {"channel": "飞书", "ok": resp.get("code") == 0 or resp.get("StatusCode") == 0,
            "detail": resp}

def _push_email(title: str, content: str) -> dict:
    """推送 SMTP 邮件（简单文本邮件）"""
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "465"))
    user = os.getenv("EMAIL_USER")
    pwd = os.getenv("EMAIL_PASS")
    to_addr = os.getenv("EMAIL_TO")
    if not all([host, user, pwd, to_addr]):
        return {"channel": "邮件", "ok": False, "detail": "邮件未配置完整，跳过"}

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = user
    msg["To"] = to_addr

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        server.login(user, pwd)
        server.sendmail(user, [to_addr], msg.as_string())
        server.quit()
        return {"channel": "邮件", "ok": True, "detail": "发送成功"}
    except Exception as e:
        return {"channel": "邮件", "ok": False, "detail": str(e)}

def _push_wecom(title: str, content: str) -> dict:
    """推送企业微信群机器人（Markdown）"""
    webhook = os.getenv("WECOM_WEBHOOK")
    if not webhook:
        return {"channel": "企业微信", "ok": False, "detail": "企业微信未配置，跳过"}
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"**{title}**\n{content[:4096]}"},
    }
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        js = resp.json()
        return {"channel": "企业微信", "ok": js.get("errcode") == 0, "detail": js}
    except Exception as e:
        return {"channel": "企业微信", "ok": False, "detail": str(e)}

def push_all(title: str, content: str, include_wecom: bool = False) -> dict:
    """向已配置的渠道推送。

    Args:
        title: 报告标题
        content: 报告正文
        include_wecom: 是否推送企业微信。默认 False（题三不发企业微信），
                       需要推送时显式传 True。

    Returns:
        {channel_name: result}
    """
    results = {}
    # 飞书（若配置了 webhook 则推送）
    if os.getenv("FEISHU_WEBHOOK"):
        results["飞书"] = _push_feishu(title, content)
    else:
        results["飞书"] = {"channel": "飞书", "ok": False, "detail": "未配置 FEISHU_WEBHOOK，跳过"}

    # 邮件（若配置了 SMTP 则推送，QQ/163/Gmail 均可）
    if os.getenv("EMAIL_HOST") and os.getenv("EMAIL_USER"):
        results["邮件"] = _push_email(title, content)
    else:
        results["邮件"] = {"channel": "邮件", "ok": False, "detail": "未配置邮件，跳过"}

    # 企业微信（默认不推送，仅当 include_wecom=True 且已配置 webhook 时推送）
    if include_wecom:
        if os.getenv("WECOM_WEBHOOK"):
            results["企业微信"] = _push_wecom(title, content)
        else:
            results["企业微信"] = {"channel": "企业微信", "ok": False, "detail": "未配置企业微信，跳过"}

    return results

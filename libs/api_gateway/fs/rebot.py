#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   rebot.py
# @Time    :   2025/06/05 16:42:01
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   飞书机器人


from string import Template
from typing import Any, Dict, List, Optional

import requests


class FeishuBot:
    def __init__(self, webhook_url: Optional[str] = None, notice_user_id: Optional[str] = None):
        """
        初始化飞书机器人
        """
        self.webhook_url = (
            webhook_url or "https://open.feishu.cn/open-apis/bot/v2/hook/71db8ab2-46bc-4383-bde2-d2d977c9bc26"
        )
        self.notice_user_id = notice_user_id or "all"
        # 预定义模板
        self.templates = {
            "instance_table": Template("""
**📊 实例信息统计**

| 实例ID | 实例名称 | 续费类型 |
|--------|----------|------|
$rows

**总计:** $total 个实例
"""),
        }

    def send_message(self, data: Dict[str, Any]):
        """
        发送消息
        """
        response = requests.post(self.webhook_url, json=data)
        if response.status_code != 200:
            raise Exception(f"飞书机器人发送消息失败: {response.text}")
        return response.json()

    def send_text_message(self, message: str):
        """
        发送文本消息
        :param message: 消息内容
        :return: 返回飞书机器人返回的消息
        """
        data = {
            "msg_type": "text",
            "content": {"text": message},
        }
        return self.send_message(data)

    def send_card_message(self, title: str, content: str):
        """
        发送卡片消息
        """
        data = {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",
                "config": {
                    "update_multi": True,
                    "style": {"text_size": {"normal_v2": {"default": "normal", "pc": "normal", "mobile": "heading"}}},
                },
                "body": {
                    "direction": "vertical",
                    "padding": "12px 12px 12px 12px",
                    "elements": [
                        {"tag": "div", "text": {"content": f"<at id={self.notice_user_id}></at>", "tag": "lark_md"}},
                        {
                            "tag": "markdown",
                            "content": content,
                            "text_align": "left",
                            "text_size": "normal_v2",
                            "margin": "0px 0px 0px 0px",
                        },
                        # {
                        #     "tag": "button",
                        #     "text": {"tag": "plain_text", "content": "🌞登录CMDB查看详情"},
                        #     "type": "default",
                        #     "width": "default",
                        #     "size": "medium",
                        #     "behaviors": [
                        #         {"type": "open_url", "default_url": "", "pc_url": "", "ios_url": "", "android_url": ""}
                        #     ],
                        #     "margin": "0px 0px 0px 0px",
                        # },
                    ],
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "subtitle": {"tag": "plain_text", "content": ""},
                    "template": "blue",
                    "padding": "12px 12px 12px 12px",
                },
            },
        }
        return self.send_message(data)

    def send_template_message(self, title: str, template_name: str, **kwargs):
        """
        使用模板发送消息
        :param title: 卡片标题
        :param template_name: 模板名称
        :param kwargs: 模板变量
        """
        if template_name not in self.templates:
            raise ValueError(f"模板 {template_name} 不存在")

        template = self.templates[template_name]
        content = template.safe_substitute(**kwargs)
        return self.send_card_message(title, content)

    def send_instance_message(self, title: str, instances: List[Dict[str, Any]]):
        """
        发送实例信息消息（使用模板）
        :param title: 卡片标题
        :param instances: 实例对象列表，格式如：[{'instance_id': 'ins-xxx', 'instance_name': 'xxx', 'renew_type': 'xxx'}]
        """
        rows = []
        for instance in instances:
            instance_id = instance.get("instance_id", "未知")
            instance_name = instance.get("instance_name", "未知")
            renew_type = instance.get("renew_type", "未知")

            rows.append(f"| {instance_id} | {instance_name} | {renew_type} |")

        return self.send_template_message(
            title=title, template_name="instance_table", rows="\n".join(rows), total=len(instances)
        )

    def send_custom_template_message(self, title: str, template_str: str, **kwargs):
        """
        使用自定义模板发送消息
        :param title: 卡片标题
        :param template_str: 模板字符串
        :param kwargs: 模板变量
        """
        template = Template(template_str)
        content = template.safe_substitute(**kwargs)
        return self.send_card_message(title, content)

    def add_template(self, name: str, template_str: str):
        """
        添加新模板
        :param name: 模板名称
        :param template_str: 模板字符串
        """
        self.templates[name] = Template(template_str)

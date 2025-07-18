#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   aliyun_billing.py
# @Time    :   2025/07/17 14:24:45
# @Author  :   shenshuo
# @Version :   1.0
# @Desc    :   阿里云账单管理

import json
from typing import Optional, Any

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest


class AliyunBilling:
    """阿里云账单管理类"""

    def __init__(
        self,
        access_id: Optional[str] = None,
        access_key: Optional[str] = None,
        region: str = "cn-hangzhou",
        account_id: str = "",
    ):
        """
        初始化阿里云账单客户端

        :param access_id: 访问密钥ID，如果为None则使用环境变量或凭据链
        :param access_key: 访问密钥Secret，如果为None则使用环境变量或凭据链
        :param region: 地域，默认为cn-hangzhou
        """
        self.region = region
        self.account_id = account_id
        if not access_id or not access_key:
            raise ValueError("阿里云账单查询需要提供 access_id 和 access_key")
        self._client = AcsClient(access_id, access_key, region)

    def query_account_balance(self) -> Any:
        """
        查询账户余额

        :return: 账户余额响应
        """
        try:
            request = CommonRequest()
            request.set_domain("business.aliyuncs.com")
            request.set_version("2017-12-14")
            request.set_action_name("QueryAccountBalance")
            request.set_method("POST")
            request.set_accept_format("json")
            response = self._client.do_action_with_exception(request)
            return json.loads(str(response, encoding="utf8"))
        except Exception as error:
            raise Exception(f"查询阿里云账户余额失败: {str(error)}")

    def get_account_balance_amount(self) -> float:
        """
        获取账户可用余额金额

        :return: 可用余额（元）
        """
        response = self.query_account_balance()
        if response.body and response.body.data:
            available_amount = response.body.data.available_amount
            if available_amount:
                # 阿里云返回的余额单位为元
                return float(str(available_amount).replace(",", ""))
            return 0.0
        return 0.0

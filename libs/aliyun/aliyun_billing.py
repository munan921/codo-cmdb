#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   aliyun_billing.py
# @Time    :   2025/07/17 14:24:45
# @Author  :   shenshuo
# @Version :   1.0
# @Desc    :   阿里云账单管理

from typing import Optional

from alibabacloud_bssopenapi20171214 import models as bss_open_api_20171214_models
from alibabacloud_bssopenapi20171214.client import Client as BssOpenApi20171214Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


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
        self._client = self._create_client(access_id, access_key)

    def _create_client(
        self, access_key_id: Optional[str] = None, access_key_secret: Optional[str] = None
    ) -> BssOpenApi20171214Client:
        """
        创建阿里云BSS OpenAPI客户端

        :param access_key_id: 访问密钥ID
        :param access_key_secret: 访问密钥Secret
        :return: BssOpenApi20171214Client
        """
        if access_key_id and access_key_secret:
            config = open_api_models.Config(access_key_id=access_key_id, access_key_secret=access_key_secret)
        else:
            # 使用凭据链，支持环境变量、实例角色等方式
            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)

        # BSS OpenAPI的endpoint
        config.endpoint = "business.aliyuncs.com"
        return BssOpenApi20171214Client(config)

    def query_account_balance(self) -> bss_open_api_20171214_models.QueryAccountBalanceResponse:
        """
        查询账户余额

        :return: 账户余额响应
        """
        runtime = util_models.RuntimeOptions()
        try:
            response = self._client.query_account_balance_with_options(runtime)
            return response
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

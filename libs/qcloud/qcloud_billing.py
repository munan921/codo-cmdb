#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   qcloud_billing.py
# @Time    :   2025/06/05 12:24:46
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   腾讯云账单管理

from typing import Any

from tencentcloud.billing.v20180709 import billing_client
from tencentcloud.billing.v20180709.models import DescribeAccountBalanceRequest, DescribeAccountBalanceResponse
from tencentcloud.common import credential


class QCloudBilling:
    def __init__(self, access_id: str, access_key: str, region: str, account_id: str):
        self.access_id = access_id
        self.access_key = access_key
        self.region = region
        self.account_id = account_id
        self.__cred = credential.Credential(access_id, access_key)
        self.client = billing_client.BillingClient(self.__cred, self.region)

    def query_balance_acct(self, request: DescribeAccountBalanceRequest = None) -> DescribeAccountBalanceResponse:
        if request is None:
            request = DescribeAccountBalanceRequest()
        response = self.client.DescribeAccountBalance(request)
        return response


if __name__ == "__main__":
    pass

#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   volc_billing.py
# @Time    :   2025/06/04 10:48:45
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   查询火山云账单

import logging
from typing import Any, List

import volcenginesdkcore
from volcenginesdkbilling import BILLINGApi, ListAvailableInstancesRequest, QueryBalanceAcctRequest


class VolCBilling:
    """
    账单
    """

    def __init__(self, access_id: str, access_key: str, region: str, account_id: str):
        self.access_id = access_id
        self.access_key = access_key
        self.region = region
        self.account_id = account_id
        self.api_instance = self.initialize_api_instance(access_id, access_key, region)

    @staticmethod
    def initialize_api_instance(access_id, access_key, region):
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_id
        configuration.sk = access_key
        configuration.region = region
        # volcenginesdkcore.Configuration.set_default(configuration)
        api_client = volcenginesdkcore.ApiClient(configuration)

        return BILLINGApi(api_client)


    def query_balance_acct(self, request=None):
        try:
            if request is None:
                request = QueryBalanceAcctRequest()
            response = self.api_instance.query_balance_acct(body=request)
        except Exception as e:
            logging.error("查询用户账户余额信息失败")
        return response


class VolCAutoRenew(VolCBilling):
    @staticmethod
    def build_request(
        instance_ids: List[str] = None, product: str = "ECS", max_results: int = 100
    ) -> ListAvailableInstancesRequest:
        """
        构建查询请求
        :param instance_ids: 实例ID列表
        :param product: 产品类型
        :param max_results: 最大查询数量
        :return: 查询请求
        """
        return ListAvailableInstancesRequest(max_results=max_results, instance_ids=instance_ids, product=product)

    def list_available_instances(self, request: ListAvailableInstancesRequest) -> Any:
        """批量查询可用实例

        Args:
            request (ListAvailableInstancesRequest): 查询请求

        Returns:
        """
        try:
            response = self.api_instance.list_available_instances(request)
            return response
        except Exception as e:
            logging.error(f"批量查询可用实例失败: {e}")
            raise e


if __name__ == "__main__":
    pass

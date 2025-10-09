# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2025/9/19
# @Description: Description

import logging

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
from volcenginesdkvpc import  VPCApi
from volcenginesdkvpc import DescribeNetworkInterfacesRequest

class VolCNetworkInterface:
    def __init__(self, access_id: str, access_key: str, region: str, account_id: str):
        self.cloud_name = "volc"
        self.page_number = 1  # 实例状态列表的页码。起始值：1 默认值：1
        self.page_size = 100  # 分页查询时设置的每页行数。最大值：100 默认值：10
        self._region = region
        self._account_id = account_id
        self._access_id = access_id
        self._access_key = access_key
        self.api_instance = self.initialize_api_instance(access_id, access_key, region)

    @staticmethod
    def initialize_api_instance(access_id, access_key, region):
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_id
        configuration.sk = access_key
        configuration.region = region
        # volcenginesdkcore.Configuration.set_default(configuration)
        api_client = volcenginesdkcore.ApiClient(configuration)
        return VPCApi(api_client)

    def get_network_interface(self, next_token):
        try:
            instances_request = DescribeNetworkInterfacesRequest()
            instances_request.next_token = next_token
            instances_request.max_results = self.page_size
            resp = self.api_instance.describe_network_interfaces(instances_request)
            return resp
        except ApiException as e:
            logging.error(f"火山云云服务器调用异常.describe_instances: {self._account_id} -- {e}")
            return None

    def get_all_network_interfaces(self):
        network_interface_list = []
        next_token = ""

        while True:
            data = self.get_network_interface(next_token)
            if data is None:
                break

            network_interface_list.extend(data.network_interface_sets)
            next_token = data.next_token

            # Break the loop if there is no next token
            if not next_token:
                break

        return network_interface_list


if __name__ == '__main__':
    pass
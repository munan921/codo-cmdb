#!/usr/bin/env python
# -*-coding:utf-8-*-
"""
Contact : 191715030@qq.com
Author  : shenshuo
Date   :  2023/11/22 11:02
Desc   :  火山云ECS主机自动发现
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
from volcenginesdkecs import DescribeInstancesRequest, ECSApi
from volcenginesdkvpc import DescribeNetworkInterfaceAttributesRequest

from libs.volc.volc_vpc import VolCVPC
from libs.volc.volc_network_interface import VolCNetworkInterface
from models.models_utils import mark_expired, mark_expired_by_sync, server_task, server_task_batch


def get_run_type(val):
    run_map = {
        "PENDING": "创建中",
        "LAUNCH_FAILED": "创建失败",
        "RUNNING": "运行中",
        "STOPPED": "关机",
        "STARTING": "开机中",
        "STOPPING": "关机中",
        "REBOOTING": "重启中",
        "SHUTDOWN": "停止待销毁",
        "TERMINATING": "销毁中",
    }
    return run_map.get(val, "未知")


def get_pay_type(val):
    pay_map = {"PrePaid": "包年包月", "PostPaid": "按量计费"}
    return pay_map.get(val, "未知")


class VolCECS:
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
        return ECSApi(api_client)

    def get_describe_info(self, next_token):
        try:
            instances_request = DescribeInstancesRequest()
            instances_request.next_token = next_token
            instances_request.max_results = self.page_size
            resp = self.api_instance.describe_instances(instances_request)
            return resp
        except ApiException as e:
            logging.error(f"火山云云服务器调用异常.describe_instances: {self._account_id} -- {e}")
            return None

    def get_all_network_interfaces(self) -> Dict[str, Any]:
        result = {}
        try:
            api_instance = VolCNetworkInterface(access_id=self._access_id, access_key=self._access_key, region=self._region, account_id=self._account_id)
            network_interfaces = api_instance.get_all_network_interfaces()
            for network_interface in network_interfaces:
                result[network_interface.network_interface_id] = network_interface.security_group_ids
        except ApiException as e:
            logging.error(f"火山云查询网卡列表失败: {self._account_id} -- {e}")
            return result
        return result


    # def get_describe_network_interface_detail(self, network_interface_id: str):
    #     """
    #     查询网卡详细信息
    #     Doc: https://api.volcengine.com/api-docs/view?serviceCode=vpc&version=2020-04-01&action=DescribeNetworkInterfaceAttributes
    #     :return:
    #     """
    #     try:
    #         instance_request = DescribeNetworkInterfaceAttributesRequest(network_interface_id=network_interface_id)
    #         resp = VolCVPC(
    #             access_id=self._access_id, access_key=self._access_key, region=self._region, account_id=self._account_id
    #         ).api_instance.describe_network_interface_attributes(instance_request)
    #         return resp
    #     except ApiException as e:
    #         logging.error(f"火山云网卡详情调用异常.get_describe_network_interface_detail: {self._account_id} -- {e}")
    #         return None

    def get_all_ecs(self):
        network_interface_map = self.get_all_network_interfaces()
        ecs_list = []
        next_token = ""
        while True:
            data = self.get_describe_info(next_token)
            if data is None:
                break

            for instance in data.instances:
                ecs_list.append(self.format_data(instance, network_interface_map))
            next_token = data.next_token
            # logging.info(f"Fetched {len(data.instances)} instances, Next token: {next_token}")

            # Break the loop if there is no next token
            if not next_token:
                break

        return ecs_list

    def format_data(self, data, network_interface_map: Dict[str, Any]) -> Dict[str, str]:
        """
        处理数据
        :param data:
        :return:
        """
        # 定义返回
        res: Dict[str, Any] = dict()
        try:
            network_interface = data.network_interfaces[0]
            vpc_id = data.vpc_id
            network_type = "经典网络" if not vpc_id else "vpc"

            res["instance_id"] = data.instance_id
            res["vpc_id"] = vpc_id
            res["state"] = get_run_type(data.status)
            res["instance_type"] = data.instance_type_id
            res["cpu"] = data.cpus
            res["memory"] = data.memory_size / 1024
            res["name"] = data.instance_name
            res["network_type"] = network_type
            res["charge_type"] = get_pay_type(data.instance_charge_type)

            # 内外网IP,可能有多个
            eip_address = data.eip_address
            inner_ip = network_interface.primary_ip_address
            res["inner_ip"] = inner_ip
            res["outer_ip"] = eip_address.ip_address if eip_address else ""

            res["os_name"] = data.os_name
            res["os_type"] = data.os_type
            res["instance_create_time"] = data.created_at
            res["instance_expired_time"] = data.expired_at
            res["region"] = self._region
            res["zone"] = data.zone_id
            res["description"] = data.description

            items = list()
            res["security_group_ids"] = list()
            network_interfaces = data.network_interfaces
            for network_interface in network_interfaces:
                network_interface_id = network_interface.network_interface_id
                security_group_ids = network_interface_map.get(network_interface_id, [])
                items.extend(security_group_ids)
            res["security_group_ids"] = list(set(items))

        except Exception as err:
            logging.error(f"火山云ECS   data format err {self._account_id} {err}")

        return res

    def sync_cmdb(
        self, cloud_name: Optional[str] = "volc", resource_type: Optional[str] = "server"
    ) -> Tuple[bool, str]:
        """
        资产信息更新到DB
        :return:
        """
        all_ecs_list: List[dict] = self.get_all_ecs()
        if not all_ecs_list:
            return False, "ECS列表为空"
        # 更新资源
        ret_state, ret_msg = server_task_batch(account_id=self._account_id, cloud_name=cloud_name, rows=all_ecs_list)
        # 标记过期
        # mark_expired(resource_type=resource_type, account_id=self._account_id)
        instance_ids = [ecs["instance_id"] for ecs in all_ecs_list]
        mark_expired_by_sync(
            cloud_name=cloud_name,
            account_id=self._account_id,
            resource_type=resource_type,
            instance_ids=instance_ids,
            region=self._region,
        )

        return ret_state, ret_msg


if __name__ == "__main__":
    pass

# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2024/3/29
# @Description: 火山云负载均衡
from __future__ import print_function

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import volcenginesdkcore
from volcenginesdkclb import (
    CLBApi,
    DescribeLoadBalancerAttributesRequest,
    DescribeLoadBalancersBillingRequest,
    DescribeLoadBalancersRequest,
)
from volcenginesdkcore.rest import ApiException

from models.models_utils import lb_task, mark_expired, mark_expired_by_sync

CLBStatusMapping = {
    "Inactive": "已停止",
    "Active": "运行中",
    "Creating": "创建中",
    "Provisioning": "创建中",
    "Configuring": "配置中",
    "Deleting": "删除中",
    "CreateFailed": "创建失败",
}

EndPointTypeMapping = {"public": "公网", "private": "私网"}

LoadBalancerBillingTypeMapping = {1: "包年包月", 2: "按量计费"}

AutoRenewMapping = {1: "自动续费", 2: "自动续费", 3: "到期不续费"}


class VolCCLB:
    def __init__(self, access_id: str, access_key: str, region: str, account_id: str):
        self.cloud_name = "volc"
        self.page_number = 1  # 实例状态列表的页码。起始值：1 默认值：1
        self.page_size = 100  # 分页查询时设置的每页行数。最大值：100 默认值：10
        self._region = region
        self._account_id = account_id
        self.api_instance = self.__initialize_api_instance(access_id, access_key, region)

    @staticmethod
    def __initialize_api_instance(access_id: str, access_key: str, region: str):
        """
        初始化api实例对象
        https://api.volcengine.com/api-sdk/view?serviceCode=clb&version=2020-04-01&language=Python
        :param access_id:
        :param access_key:
        :param region:
        :return:
        """
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_id
        configuration.sk = access_key
        configuration.region = region
        configuration.client_side_validation = False
        # set default configuration
        # volcenginesdkcore.Configuration.set_default(configuration)
        api_client = volcenginesdkcore.ApiClient(configuration)
        return CLBApi(api_client)

    def get_describe_load_balancers(self):
        """
        接口查询CLB实例的基本信息
        Doc: https://api.volcengine.com/api-docs/view?serviceCode=clb&version=2020-04-01&action=DescribeLoadBalancers
        :return:
        """
        try:
            instances_request = DescribeLoadBalancersRequest(page_number=self.page_number, page_size=self.page_size)
            resp = self.api_instance.describe_load_balancers(instances_request)
            return resp
        except ApiException as e:
            logging.error(f"火山云负载均衡CLB调用异常 get_describe_load_balancers: {self._account_id} -- {e}")

            return None

    def get_describe_load_balancer_detail(self, load_balancer_id: str) -> dict:
        """
        接口查询CLB实例的详细信息
        Doc: https://api.volcengine.com/api-docs/view?serviceCode=clb&version=2020-04-01&action=DescribeLoadBalancerAttributes
        :return:
        """
        try:
            instances_request = DescribeLoadBalancerAttributesRequest(load_balancer_id=load_balancer_id)
            resp = self.api_instance.describe_load_balancer_attributes(instances_request)
            return resp
        except ApiException as e:
            logging.error(
                f"火山云负载均衡CLB实例详情调用异常 get_describe_load_balancer_detail: {self._account_id} -- {e}"
            )
            return None

    def describe_load_balancer_billing(
        self, load_balancer_ids: List[str], page_number: int = 1, page_size: int = 20
    ) -> dict:
        """
        接口查询CLB实例的计费信息
        Doc: https://api.volcengine.com/api-docs/view?serviceCode=clb&version=2020-04-01&action=DescribeLoadBalancersBilling
        :return:
        """
        try:
            instances_request = DescribeLoadBalancersBillingRequest()
            instances_request.load_balancer_ids = load_balancer_ids
            instances_request.page_number = page_number
            instances_request.page_size = page_size
            resp = self.api_instance.describe_load_balancers_billing(instances_request)
            return resp
        except ApiException as e:
            logging.error(
                f"火山云负载均衡CLB实例计费信息调用异常 describe_load_balancer_billing: {self._account_id} -- {e}"
            )
            return None

    def get_all_load_balancer_billing_map(self, load_balancer_ids: List[str]) -> Dict[str, Any]:
        """
        批量查询所有CLB实例的计费信息并汇总成map对象
        :param load_balancer_ids: 负载均衡实例ID列表
        :return: 以实例ID为key的计费信息map
        """
        billing_map = {}
        if not load_balancer_ids:
            return billing_map

        try:
            # 按批次查询，每次最多20个实例
            batch_size = 20
            for i in range(0, len(load_balancer_ids), batch_size):
                batch_ids = load_balancer_ids[i:i + batch_size]

                billing_data = self.describe_load_balancer_billing(
                    load_balancer_ids=batch_ids,
                    page_number=1,
                )

                if billing_data is None or not hasattr(billing_data, 'load_balancer_billing_configs'):
                    continue

                billing_configs = billing_data.load_balancer_billing_configs
                if not billing_configs:
                    continue

                # 将计费信息存入map
                for billing_config in billing_configs:
                    if hasattr(billing_config, 'load_balancer_id'):
                        billing_map[billing_config.load_balancer_id] = billing_config

        except Exception as e:
            logging.error(f"批量查询CLB计费信息异常 get_all_load_balancer_billing_map: {self._account_id} -- {e}")

        return billing_map

    def get_single_billing(self, load_balancer_id: str) -> dict:
        """
        接口查询CLB实例的计费信息
        Doc: https://api.volcengine.com/api-docs/view?serviceCode=clb&version=2020-04-01&action=DescribeLoadBalancerBilling
        :return:
        """
        billing_info = self.describe_load_balancer_billing([load_balancer_id])
        if billing_info is not None:
            try:
                billing_info = billing_info.load_balancer_billing_configs[0]
                return billing_info
            except Exception as e:
                logging.error(f"火山云负载均衡CLB实例计费信息调用异常 get_single_billing: {self._account_id} -- {e}")
                return {}
        return {}

    def get_all_clbs(self):
        clbs = list()
        all_instances = []
        try:
            # 首先获取所有实例
            while True:
                data = self.get_describe_load_balancers()
                if data is None:
                    break

                instances = data.load_balancers
                if not instances:
                    break
                all_instances.extend(instances)
                total_count = data.total_count
                if total_count < self.page_size:
                    break
                self.page_number += 1

            # 批量查询计费信息
            load_balancer_ids = [instance.load_balancer_id for instance in all_instances]
            billing_map = self.get_all_load_balancer_billing_map(load_balancer_ids)

            # 处理数据
            clbs.extend([self.handle_data(instance, billing_map) for instance in all_instances])

        except Exception as e:
            logging.error(f"火山云负载均衡调用异常 get_all_clbs: {self._account_id} -- {e}")
        return clbs

    def handle_data(self, data, billing_map: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        数据加工处理
        :param data: 负载均衡实例数据
        :param billing_map: 计费信息map
        :return:
        """
        res: Dict[str, Any] = dict()
        res["type"] = "clb"
        res["name"] = data.load_balancer_name
        res["instance_id"] = data.load_balancer_id
        res["create_time"] = data.create_time
        res["region"] = self._region
        res["lb_vip"] = data.eip_address or data.eni_address  # 火山云clb有公网和私网 这里优先取公网,无公网取私网
        res["zone"] = data.master_zone_id
        res["status"] = CLBStatusMapping.get(data.status, "未知")
        res["dns_name"] = ""
        res["endpoint_type"] = EndPointTypeMapping.get(data.type, "未知")
        lb_vips = [data.eni_address]
        eni_address = data.eni_address
        if eni_address:
            lb_vips.append(eni_address)

        res["ext_info"] = {
            "vpc_id": data.vpc_id,
            "lb_vips": lb_vips,
            "ip_version": data.address_ip_version,
            "slave_zone_id": data.slave_zone_id,
        }

        detail = self.get_describe_load_balancer_detail(data.load_balancer_id)
        if detail is not None:
            res["ext_info"]["charge_type"] = LoadBalancerBillingTypeMapping.get(
                detail.load_balancer_billing_type, ""
            )

        # 使用批量查询的计费信息map，如果没有则使用单个查询
        billing_info = None
        if billing_map and data.load_balancer_id in billing_map:
            billing_info = billing_map[data.load_balancer_id]
        else:
            billing_info = self.get_single_billing(data.load_balancer_id)

        if billing_info is not None:
            res["ext_info"]["renew_type"] = AutoRenewMapping.get(billing_info.renew_type, "")
        return res

    def sync_cmdb(self, cloud_name: Optional[str] = "volc", resource_type: Optional[str] = "lb") -> Tuple[bool, str]:
        """
        同步到DB
        :param cloud_name:
        :param resource_type:
        :return:
        """
        clbs: List[dict] = self.get_all_clbs()
        if not clbs:
            return False, "clb列表为空"
        # 更新资源
        ret_state, ret_msg = lb_task(account_id=self._account_id, cloud_name=cloud_name, rows=clbs)
        # 标记过期
        # mark_expired(resource_type=resource_type, account_id=self._account_id)
        instance_ids = [lb["instance_id"] for lb in clbs]
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

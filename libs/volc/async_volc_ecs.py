#!/usr/bin/env python
# -*-coding:utf-8-*-
"""
Contact : 191715030@qq.com
Author  : shenshuo
Date   :  2023/11/22 11:02
Desc   :  火山云ECS主机自动发现 - 异步版本
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
from volcenginesdkecs import DescribeInstancesRequest, ECSApi
from volcenginesdkvpc import DescribeNetworkInterfaceAttributesRequest

from libs.volc.volc_vpc import VolCVPC
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


class VolCECSAsync:
    def __init__(self, access_id: str, access_key: str, region: str, account_id: str):
        self.cloud_name = "volc"
        self.page_size = 100
        self._region = region
        self._account_id = account_id
        self._access_id = access_id
        self._access_key = access_key
        self.api_instance = self.initialize_api_instance(access_id, access_key, region)
        self.vpc_api_instance = self.initialize_vpc_api_instance(access_id, access_key, region)

        # 信号量控制并发数，避免API限流
        self.semaphore = asyncio.Semaphore(10)  # 最大并发10个请求

    @staticmethod
    def initialize_api_instance(access_id, access_key, region):
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_id
        configuration.sk = access_key
        configuration.region = region
        volcenginesdkcore.Configuration.set_default(configuration)
        return ECSApi()

    @staticmethod
    def initialize_vpc_api_instance(access_id, access_key, region):
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_id
        configuration.sk = access_key
        configuration.region = region
        return VolCVPC(access_id, access_key, region, "").api_instance

    async def get_describe_info_async(self, next_token: str = ""):
        """异步获取ECS实例信息"""
        async with self.semaphore:  # 控制并发
            try:
                instances_request = DescribeInstancesRequest()
                instances_request.next_token = next_token
                instances_request.max_results = self.page_size

                # 使用async_req=True进行异步调用
                thread = self.api_instance.describe_instances(instances_request, async_req=True)
                # 在asyncio中等待线程完成
                result = await asyncio.get_event_loop().run_in_executor(None, thread.get)
                return result

            except ApiException as e:
                logging.error(f"火山云云服务器异步调用异常.describe_instances: {self._account_id} -- {e}")
                return None

    async def get_describe_network_interface_detail_async(self, network_interface_id: str):
        """异步查询网卡详细信息"""
        async with self.semaphore:  # 控制并发
            try:
                instance_request = DescribeNetworkInterfaceAttributesRequest(network_interface_id=network_interface_id)

                # 使用async_req=True进行异步调用
                thread = self.vpc_api_instance.describe_network_interface_attributes(instance_request, async_req=True)
                result = await asyncio.get_event_loop().run_in_executor(None, thread.get)
                return result

            except ApiException as e:
                logging.error(f"火山云网卡详情异步调用异常: {self._account_id} -- {e}")
                return None

    async def format_data_async(self, data) -> Dict[str, Any]:
        """异步处理数据格式化"""
        res: Dict[str, Any] = dict()
        try:
            network_interface = data.network_interfaces[0] if data.network_interfaces else None
            vpc_id = data.vpc_id
            network_type = "经典网络" if not vpc_id else "vpc"

            # 基础数据处理（同步部分）
            res["instance_id"] = data.instance_id
            res["vpc_id"] = vpc_id
            res["state"] = get_run_type(data.status)
            res["instance_type"] = data.instance_type_id
            res["cpu"] = data.cpus
            res["memory"] = data.memory_size / 1024
            res["name"] = data.instance_name
            res["network_type"] = network_type
            res["charge_type"] = get_pay_type(data.instance_charge_type)

            # 内外网IP
            eip_address = data.eip_address
            inner_ip = network_interface.primary_ip_address if network_interface else ""
            res["inner_ip"] = inner_ip
            res["outer_ip"] = eip_address.ip_address if eip_address else ""

            res["os_name"] = data.os_name
            res["os_type"] = data.os_type
            res["instance_create_time"] = data.created_at
            res["instance_expired_time"] = data.expired_at
            res["region"] = self._region
            res["zone"] = data.zone_id
            res["description"] = data.description

            # 异步并发获取网络接口详情
            security_group_ids = []
            if data.network_interfaces:
                # 创建异步任务列表
                network_interface_tasks = [
                    self.get_describe_network_interface_detail_async(ni.network_interface_id)
                    for ni in data.network_interfaces
                ]

                # 并发执行所有网络接口查询
                network_details = await asyncio.gather(*network_interface_tasks, return_exceptions=True)

                # 处理结果
                for detail in network_details:
                    if detail and not isinstance(detail, Exception) and hasattr(detail, "security_group_ids"):
                        security_group_ids.extend(detail.security_group_ids)

            res["security_group_ids"] = security_group_ids

        except Exception as err:
            logging.error(f"火山云ECS异步数据格式化错误 {self._account_id} {err}")

        return res

    async def get_all_ecs_async(self) -> List[Dict[str, Any]]:
        """异步获取所有ECS实例"""
        all_ecs_list = []
        next_token = ""

        logging.info(f"开始异步获取火山云ECS实例 - {self._account_id}")

        while True:
            # 异步获取分页数据
            data = await self.get_describe_info_async(next_token)
            if data is None:
                break

            instances = data.instances
            if not instances:
                break

            logging.info(f"获取到 {len(instances)} 个实例，开始异步处理...")

            # 异步并发处理所有实例数据
            format_tasks = [self.format_data_async(instance) for instance in instances]
            formatted_instances = await asyncio.gather(*format_tasks, return_exceptions=True)

            # 过滤有效结果
            valid_instances = [
                inst
                for inst in formatted_instances
                if inst and not isinstance(inst, Exception) and inst.get("instance_id")
            ]

            all_ecs_list.extend(valid_instances)
            next_token = data.next_token

            logging.info(f"已处理 {len(valid_instances)} 个有效实例，累计: {len(all_ecs_list)}")

            if not next_token:
                break

        logging.info(f"异步获取完成，总计 {len(all_ecs_list)} 个ECS实例")
        return all_ecs_list

    async def sync_cmdb_async(
        self, cloud_name: Optional[str] = "volc", resource_type: Optional[str] = "server"
    ) -> Tuple[bool, str]:
        """异步同步ECS数据到CMDB - 数据获取异步，数据库写入同步"""
        try:
            # 异步获取所有ECS数据
            logging.info(f"开始异步同步火山云ECS数据 - {self._account_id}")
            all_ecs_list = await self.get_all_ecs_async()

            if not all_ecs_list:
                return False, "ECS列表为空"

            logging.info(f"异步数据获取完成，共 {len(all_ecs_list)} 个实例，开始同步写入数据库...")

            # 数据库写入使用同步方式（因为数据库操作本身是同步的）
            ret_state, ret_msg = server_task_batch(
                account_id=self._account_id, cloud_name=cloud_name, rows=all_ecs_list
            )

            if ret_state:
                # 同步标记过期实例
                instance_ids = [ecs["instance_id"] for ecs in all_ecs_list]
                mark_expired_by_sync(
                    cloud_name=cloud_name,
                    account_id=self._account_id,
                    resource_type=resource_type,
                    instance_ids=instance_ids,
                    region=self._region,
                )
                logging.info(f"数据库同步完成 - {self._account_id}")

            return ret_state, ret_msg

        except Exception as e:
            error_msg = f"异步同步CMDB失败: {str(e)}"
            logging.error(error_msg)
            return False, error_msg


# 异步同步函数
async def sync_volc_ecs_async(access_id: str, access_key: str, region: str, account_id: str):
    """异步同步火山云ECS数据"""
    try:
        volc_ecs = VolCECSAsync(access_id, access_key, region, account_id)
        success, message = await volc_ecs.sync_cmdb_async()
        logging.info(f"异步同步结果 - {account_id}: {success}, {message}")
        return success, message
    except Exception as e:
        error_msg = f"异步同步异常 - {account_id}: {str(e)}"
        logging.error(error_msg)
        return False, error_msg


# 兼容原有同步接口的包装器
def sync_volc_ecs_wrapper(access_id: str, access_key: str, region: str, account_id: str):
    """同步接口包装器，内部使用异步实现"""
    try:
        # 创建新的事件循环（如果当前线程没有的话）
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 运行异步函数
        return loop.run_until_complete(sync_volc_ecs_async(access_id, access_key, region, account_id))
    except Exception as e:
        error_msg = f"同步包装器异常 - {account_id}: {str(e)}"
        logging.error(error_msg)
        return False, error_msg


# 为了保持向后兼容，可以替换原有的VolCECS类
class VolCECS(VolCECSAsync):
    """向后兼容的同步接口类"""

    def sync_cmdb(
        self, cloud_name: Optional[str] = "volc", resource_type: Optional[str] = "server"
    ) -> Tuple[bool, str]:
        """同步接口，内部使用异步实现"""
        return sync_volc_ecs_wrapper(self._access_id, self._access_key, self._region, self._account_id)


if __name__ == "__main__":
    pass
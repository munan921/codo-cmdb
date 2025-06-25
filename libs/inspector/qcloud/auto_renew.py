#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   auto_renew.py
# @Time    :   2025/06/05 14:37:39
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   自动续费巡检
from typing import Any, List, Optional

from libs.inspector.base import BaseInspector, InspectorResult, InspectorStatus


class QCloudAutoRenewInspector(BaseInspector):
    """
    腾讯云自动续费巡检器
    """

    def __init__(self, instance_objs: List[Any], resource_type: Optional[str] = None):
        super().__init__()
        self.instance_objs = instance_objs
        self.resource_type = resource_type

    def run(self) -> InspectorResult:
        """
        执行腾讯云自动续费巡检, 返回未自动续费的实例列表
        :return: BaseInspectorResult, 包含成功状态、消息和数据
        """
        # Optimize: 可以优化为批量查询
        if not self.instance_objs:
            return InspectorResult(success=False, message="腾讯云未获取到有效的实例列表", status=InspectorStatus.NORMAL)

        result = []
        for instance in self.instance_objs:
            ext_info = instance.get("ext_info")
            if ext_info.get("renew_type", "") != "自动续费" and ext_info.get("charge_type", "") == "包年包月":
                result.append(
                    dict(
                        instance_id=instance["instance_id"],
                        instance_name=instance["instance_name"],
                        renew_type=ext_info.get("renew_type", ""),
                    )
                )
        if not result:
            return InspectorResult(
                success=True, message="腾讯云包年包年未自动续费实例为空", status=InspectorStatus.NORMAL
            )
        return InspectorResult(
            success=True, message="腾讯云包年包月未自动续费实例列表", data=result, status=InspectorStatus.EXCEPTION
        )

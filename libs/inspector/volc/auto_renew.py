#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File:   billing.py
# @Time:   2025/06/04 15:48:18
# @Author:   DongdongLiu
# @Version:  1.1
# @Desc:     火山云自动续费巡检逻辑

from typing import Any, Dict, List

from volcenginesdkbilling import ListAvailableInstancesRequest

from libs.inspector.base import BaseInspector, InspectorResult, InspectorStatus
from libs.volc.volc_billing import VolCAutoRenew


class VolCAutoRenewInspector(BaseInspector):
    def __init__(
        self,
        instance_obj: VolCAutoRenew,
        request: ListAvailableInstancesRequest,
    ) -> None:
        super().__init__()
        self.instance_obj = instance_obj
        self.request = request

    def run(self) -> InspectorResult:
        """
        获取实例信息，并筛选出非自动续费的实例
        """
        response = self.instance_obj.list_available_instances(self.request)
        if not hasattr(response, "instance_list") or not response.instance_list:
            self.logger.warning(f"未获取到有效的实例列表: {response}")
            return InspectorResult(success=False, message="未获取到有效的实例列表", status=InspectorStatus.NORMAL)

        data = self._filter_non_autorenew_instance(response.instance_list)
        if not data:
            return InspectorResult(success=True, message="全部实例为自动续费", status=InspectorStatus.NORMAL)
        return InspectorResult(
            success=True, message="存在未自动续费的实例", data=data, status=InspectorStatus.EXCEPTION
        )

    @staticmethod
    def _filter_non_autorenew_instance(instances: List[Any]) -> List[Dict[str, Any]]:
        """
        过滤出非自动续费实例
        """
        # FIXME: 自动续费类型为AutoRenewal，手动续费类型为ManualRenewal
        return [
            {"instance_id": ins.instance_id, "renew_type": "手动续费", "instance_name": ins.instance_name}
            for ins in instances
            if ins.renew_type and ins.renew_type != "AutoRenewal"
        ]

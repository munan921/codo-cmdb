#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   billing.py
# @Time    :   2025/07/17 14:24:45
# @Author  :   shenshuo
# @Version :   1.0
# @Desc    :   阿里云账单巡检

from libs.aliyun.aliyun_billing import AliyunBilling
from libs.inspector.base import BaseInspector, InspectorResult, InspectorStatus


class AliyunBillingInspector(BaseInspector):
    """
    阿里云账单余额巡检器

    用于检查阿里云账户的可用余额是否低于设定的阈值
    """

    def __init__(self, instance_obj: AliyunBilling, threshold: float = 1000000.0):
        super().__init__()
        try:
            self.threshold = float(threshold)
        except ValueError:
            raise ValueError("阈值必须为数字")
        if self.threshold < 0:
            raise ValueError("阈值不能为负数")
        self.instance_obj = instance_obj

    def run(self) -> InspectorResult:
        """
        执行阿里云账单余额巡检，获取账户余额
        :return: InspectorResult
        """
        try:
            response = self.instance_obj.query_account_balance()
        except Exception as e:
            return InspectorResult(
                success=False,
                message=str(e),
                status=InspectorStatus.EXCEPTION,
            )

        if response.get("Code") != "200":
            return InspectorResult(
                success=False,
                message=response.get("Message"),
                status=InspectorStatus.EXCEPTION,
            )

        # 可用余额
        # NOTE 可用余额计算方式: （现金余额 + 信用额度）- （当月未结清 + 历史未结清）
        available_amount = float(response.get("Data", {}).get("AvailableAmount", "").replace(",", ""))
        if not available_amount:
            return InspectorResult(
                success=False,
                message="未获取到有效的可用余额",
                status=InspectorStatus.EXCEPTION,
            )

        # 检查余额是否低于阈值
        if available_amount < self.threshold:
            return InspectorResult(
                success=True,
                message=f"阿里云账户可用余额(包含信控)巡检异常，当前余额为{available_amount}元, 小于阈值{self.threshold}元",
                status=InspectorStatus.EXCEPTION,
            )
        return InspectorResult(
            success=True,
            message=f"阿里云账户可用余额巡检(包含信控)正常，当前余额为{available_amount}元, 大于阈值{self.threshold}元",
            status=InspectorStatus.NORMAL,
        )

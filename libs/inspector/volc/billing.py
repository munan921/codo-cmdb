#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   billing.py
# @Time    :   2025/06/04 18:37:49
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   火山云账单巡检
from libs.inspector.base import BaseInspector, InspectorResult, InspectorStatus
from libs.volc.volc_billing import VolCBilling


class VolCBillingInspector(BaseInspector):
    """
    火山云账单余额巡检器

    用于检查火山云账户的可用余额是否低于设定的阈值
    """

    def __init__(self, instance_obj: VolCBilling, threshold: float = 200000.0) -> None:
        """
        初始化账单巡检器

        Args:
            instance_obj: 火山云账单客户端实例
            threshold: 余额告警阈值，默认200000.0

        Raises:
            ValueError: 当threshold为负数时抛出
        """
        super().__init__()
        try:
            self.threshold = float(threshold)
        except ValueError:
            raise ValueError("阈值必须为数字")
        if self.threshold < 0:
            raise ValueError("阈值不能为负数")
        self.client = instance_obj

    def run(self) -> InspectorResult:
        """
        执行火山云账单余额巡检

        Returns:
            InspectorResult: 巡检结果，包含成功状态、消息和余额数据
        """
        response = self.client.query_balance_acct()
        if not response or not response.available_balance:
            self.logger.error("火山云账单余额请求返回异常")
            return InspectorResult(success=False, message="查询火山云余额失败")

        # 处理余额数据类型
        try:
            balance = float(response.available_balance)
        except (ValueError, TypeError) as e:
            self.logger.exception(f"解析可用余额失败: {e}")
            return InspectorResult(success=False, message="解析可用余额失败")

        # 比较阈值
        if balance < self.threshold:
            return InspectorResult(
                success=True,
                status=InspectorStatus.EXCEPTION,
                message=f"火山云账户可用余额巡检异常，当前余额为{balance}元, 小于阈值{self.threshold}元",
            )
        return InspectorResult(
            success=True,
            status=InspectorStatus.NORMAL,
            message=f"火山云账户可用余额巡检正常，当前余额为{balance}元, 大于阈值{self.threshold}元",
        )

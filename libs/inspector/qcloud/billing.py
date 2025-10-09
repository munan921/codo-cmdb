#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   billing.py
# @Time    :   2025/06/05 14:24:45
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   账单巡检

from libs.inspector.base import BaseInspector, InspectorResult, InspectorStatus
from libs.qcloud.qcloud_billing import QCloudBilling


class QCloudBillingInspector(BaseInspector):
    """
    腾讯云账单余额巡检器

    用于检查腾讯云账户的可用余额是否低于设定的阈值
    """

    def __init__(self, instance_obj: QCloudBilling, threshold: float = 1000000.0):
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
        执行腾讯云账单余额巡检，获取账户余额
        :return: InspectorResult
        """
        response = self.instance_obj.query_balance_acct()
        if not hasattr(response, "Balance"):
            return InspectorResult(
                success=False,
                message="未获取到有效的账单余额",
                status=InspectorStatus.EXCEPTION,
            )
        # 信用额度
        credit_amount = response.CreditAmount
        # 当前真实可用余额
        real_balance = response.RealBalance
        # 赠送余额
        present_account_balance = response.PresentAccountBalance
        # 冻结金额
        freeze_account = response.FreezeAmount
        # 欠费金额
        owe_amount = response.OweAmount

        # 余额单位为分，转为元
        total_balance = (credit_amount + real_balance + present_account_balance - owe_amount - freeze_account) / 100
        # 计算信用额度 + 当前真实可用余额 < 阈值
        if float(total_balance) < self.threshold:
            return InspectorResult(
                success=True,
                message=f"腾讯云账户可用余额(包含信控)巡检异常，当前余额为{total_balance}元, 小于阈值{self.threshold}元",
                status=InspectorStatus.EXCEPTION,
            )
        return InspectorResult(
            success=True,
            message=f"腾讯云账户可用余额(包含信控)巡检正常，当前余额为{total_balance}元, 大于阈值{self.threshold}元",
            status=InspectorStatus.NORMAL,
        )

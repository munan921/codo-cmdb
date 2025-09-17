# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2025/8/30
# @Description: Description

import json
from abc import ABC
from libs.base_handler import BaseHandler
from services.cloud_billing_service import create_or_update, get_cloud_billing_settings


class CloudBillingHandlers(BaseHandler, ABC):
    def get(self):
        res = get_cloud_billing_settings()
        return self.write(res)

    def post(self):
        data = json.loads(self.request.body.decode("utf-8"))
        res = create_or_update(**data)
        return self.write(res)

    def put(self):
        data = json.loads(self.request.body.decode("utf-8"))
        res = create_or_update(**data)
        return self.write(res)


cloud_billing_urls = [
    (r"/api/v2/cmdb/cloud/billing/conf/", CloudBillingHandlers, {"handle_name": "配置平台-云厂商-账单巡检", "method": ["GET"]}),
]
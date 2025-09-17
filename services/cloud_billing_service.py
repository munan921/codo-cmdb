# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2025/8/30
# @Description: Description
from typing import List
from urllib.parse import urlparse

from apscheduler.triggers.cron import CronTrigger
from websdk2.db_context import DBContextV2 as DBContext
from websdk2.model_utils import CommonOptView, model_to_dict, queryset_to_list

from libs.scheduled_tasks import reload_single_billing_task
from libs.mycrypt import mc
from models.cloud import CloudBillingSettingModels, CloudSettingModels

opt_obj = CommonOptView(CloudBillingSettingModels)


def validate_cron(expr: str = '') -> bool:
    if not expr or not isinstance(expr, str):
        return False

    fields = expr.split()
    try:
        if len(fields) == 5:
            CronTrigger.from_crontab(expr)
        elif len(fields) == 6:  # 支持秒
            CronTrigger(second=fields[0], minute=fields[1], hour=fields[2],
                        day=fields[3], month=fields[4], day_of_week=fields[5])
        else:
            return False
        return True
    except Exception as e:
        return False

def validate_webhook_url(url: str = '') -> bool:
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    # URL必须有scheme和netloc
    if parsed.scheme not in ('http', 'https'):
        return False
    if not parsed.netloc:
        return False

    return True

def _handle_webhook_secret(webhook_secret, existing_obj):
  """处理webhook密钥加密逻辑"""
  if not webhook_secret:
      return ""

  # 如果没有现有对象，或现有对象没有密钥，或密钥不同，则加密新密钥
  if (not existing_obj or
      not existing_obj.webhook_secret or
      webhook_secret != existing_obj.webhook_secret):
      return mc.my_encrypt(webhook_secret)

  # 密钥相同，保持原值
  return existing_obj.webhook_secret


def create_or_update(**data):
    cloud_setting_id = data.get('cloud_setting_id', 0)
    if not cloud_setting_id:
        return {"code": -1, "msg": "云厂商配置id不能为空"}

    threshold = data.get("threshold", 0)
    if not threshold:
        return {"code": -1, "msg": "阈值不能为空"}
    try:
        float(threshold)
    except ValueError:
        return {"code": -1, "msg": "阈值必须为数字"}

    scheduled_expr = data.get("scheduled_expr", "")
    if not scheduled_expr:
        return {"code": -1, "msg": "调度表达式不能为空"}

    if not validate_cron(scheduled_expr):
        return {"code": -1, "msg": "调度表达式不合法"}

    webhook_url = data.get("webhook_url", "")
    if not webhook_url:
        return {"code": -1, "msg": "webhook地址不能为空"}

    webhook_type = data.get("webhook_type", "feishu")

    try:
        is_valid = validate_webhook_url(webhook_url)
        if not is_valid:
            return {"code": -1, "msg": "webhook地址格式不正确"}
    except ValueError:
        return {"code": -1, "msg": "webhook地址格式不正确"}

    webhook_secret = data.get("webhook_secret", "").strip()


    kw = {
        "cloud_setting_id": cloud_setting_id,
        "threshold": threshold,
        "scheduled_expr": scheduled_expr,
        "webhook_type": webhook_type,
        "webhook_url": webhook_url,
    }

    try:
        with DBContext('w', None, True) as session:
            cloud_setting_obj = session.query(CloudSettingModels).filter(
                CloudSettingModels.id == cloud_setting_id).first()
            if not cloud_setting_obj:
                return {"code": -1, "msg": "云厂商配置不存在"}
            existing_obj = session.query(CloudBillingSettingModels).filter(
                CloudBillingSettingModels.cloud_setting_id == cloud_setting_id).first()

            # 处理webhook密钥，这里的密钥回显是密文，不会导致安全风险
            kw["webhook_secret"] = _handle_webhook_secret(webhook_secret, existing_obj)

            if not existing_obj:
                session.add(CloudBillingSettingModels(**kw))
            else:
                session.query(CloudBillingSettingModels).filter(
                    CloudBillingSettingModels.cloud_setting_id == cloud_setting_id).update(kw)

            session.commit()
    except Exception as e:
        return dict(code=-1, msg="添加云厂商账单巡检配置失败")
    reload_single_billing_task(cloud_setting_id=cloud_setting_id)
    return dict(code=0, msg="添加云厂商账单巡检配成功")


def get(**params) -> dict:
    cloud_setting_id = params.get("cloud_setting_id")
    if not cloud_setting_id:
        return {"code": -1, "msg": "云厂商配置ID不能为空"}

    try:
        with DBContext('r') as session:
            obj = (
                session.query(CloudBillingSettingModels)
                .filter_by(cloud_setting_id=cloud_setting_id)
            ).first()
            if not obj:
                return {"code": -1, "msg": "未找到云厂商账单配置"}
            return {"code": 0, "msg": "success", "data": model_to_dict(obj)}
    except Exception as e:
        return {"code": -1, "msg": f"查询失败: {e}"}


def get_cloud_billing_settings() -> dict:
    with DBContext('r', None, None) as session:
        cloud_billing_setting_info: List[CloudBillingSettingModels] = session.query(CloudBillingSettingModels).all()
        cloud_billing_list: List[dict] = queryset_to_list(cloud_billing_setting_info)
    return dict(msg='获取成功', code=0, data=cloud_billing_list)

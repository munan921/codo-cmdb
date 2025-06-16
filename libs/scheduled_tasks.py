# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2025/2/13
# @Description: Description

import datetime
import logging
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set

from websdk2.api_set import api_set
from websdk2.client import AcsClient
from websdk2.configs import configs
from websdk2.db_context import DBContext
from websdk2.model_utils import queryset_to_list
from websdk2.tools import RedisLock

from libs import deco
from libs.api_gateway.fs.rebot import FeishuBot
from libs.inspector.base import InspectorStatus, InspectorResult
from libs.inspector.qcloud.auto_renew import QCloudAutoRenewInspector
from libs.inspector.qcloud.billing import QCloudBillingInspector
from libs.inspector.volc.auto_renew import VolCAutoRenewInspector
from libs.inspector.volc.billing import VolCBillingInspector
from libs.mycrypt import MyCrypt
from libs.qcloud.qcloud_billing import QCloudBilling
from libs.scheduler import scheduler
from libs.volc.volc_billing import VolCAutoRenew, VolCBilling
from models import TreeAssetModels, asset_mapping
from models.agent import AgentModels
from models.asset import AgentBindStatus, AssetServerModels
from models.cloud import CloudSettingModels
from models.models_utils import get_cloud_config
from services.asset_server_service import get_unique_servers
from services.cloud_region_service import get_servers_by_cloud_region_id
from settings import settings

if configs.can_import:
    configs.import_dict(**settings)

mc = MyCrypt()


def send_router_alert(params: dict, body: dict):
    """
    发送告警
    """
    client = AcsClient()
    api_set.send_router_alert.update(
        params=params,
        body=body,
    )
    try:
        resp = client.do_action_v2(**api_set.send_router_alert)
        if resp.status_code != 200:
            logging.error(f"发送告警到NOC失败 {resp.status_code}")
    except Exception as err:
        logging.error(f"发送告警到NOC出错 {err}")


def bind_agent_tasks():
    """
    检查agent是否能绑定主机
    如果能绑定则更新agent的asset_server_id，同时更新server的agent_id
    """

    @deco(RedisLock("agent_binding_tasks_redis_lock_key"), release=True)
    def index():
        logging.info("开始agent绑定主机！！！")
        bind_agents()
        logging.info("agent绑定主机结束！！！")

    try:
        index()
    except Exception as err:
        logging.error(f"agent绑定主机出错 {str(err)}")


def bind_agents() -> Set[str]:
    """
    绑定agent到服务器
    :return: 未绑定的agent ID集合
    """
    unbound_agents = set()
    with DBContext("w", None, True) as session:
        agents = session.query(AgentModels).all()
        unique_servers = get_unique_servers()
        for agent in agents:
            # 若agent已绑定，则跳过
            if agent.asset_server_id:
                continue
            try:
                matched_server = find_matched_server(agent, unique_servers)
                if not matched_server:
                    unbound_agents.add(f"【{agent.hostname}|{agent.ip}|{agent.agent_id}】")
                    continue

                # 更新agent的asset_server_id
                agent.asset_server_id = matched_server.id
                agent.agent_bind_status = AgentBindStatus.AUTO_BIND
                # 更新server的agent_id 只更新增量数据, 忽略存量数据
                if matched_server.agent_id == "0":
                    server = session.query(AssetServerModels).filter(AssetServerModels.id == matched_server.id).first()
                    server.agent_id = agent.agent_id
                    server.agent_bind_status = AgentBindStatus.AUTO_BIND
            except Exception as err:
                logging.error(f"更新agent出错 {str(err)}")
        session.commit()
    return unbound_agents


def find_matched_server(agent: AgentModels, unique_servers: Dict[str, AssetServerModels]) -> AssetServerModels:
    """
    查找匹配的服务器
    :param agent: Agent对象
    :param unique_servers: 唯一服务器字典
    :return: 匹配的服务器对象或None
    """
    # 查找云区域关联的云主机, 且云主机没有设置主agent，已绑定主agent的云主机不再绑定
    servers = get_servers_by_cloud_region_id(agent.proxy_id)
    for server in servers:
        if server.inner_ip == agent.ip and server.state == "运行中" and not server.has_main_agent:
            return server

    # 若 servers 没匹配到，则在 unique_servers 里找
    return unique_servers.get(agent.ip)


def notify_unbound_agents_tasks(unbound_agents: Set[str] = None) -> None:
    """
    发送未匹配agent的告警
    :param unbound_agents: 未匹配的agent ID集合
    """

    @deco(RedisLock("notify_unbound_agents_tasks_redis_lock_key"))
    def index():
        unbound_agents = bind_agents()
        if unbound_agents:
            body = {
                "agent_ids": "\n".join(list(unbound_agents)),
                "alert_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "title": "【CMDB】agent未匹配主机",
            }
            send_router_alert(params={"cmdb_agent_not_match": 1}, body=body)

    try:
        index()
    except Exception as err:
        logging.error(f"发送未匹配agent告警出错 {str(err)}")


def filter_ingore_tree_alert_servers(servers: List[AssetServerModels]) -> List[AssetServerModels]:
    """
    过滤掉不需要发送告警的服务器
    :param servers: 服务器列表
    :return: 过滤后的服务器列表
    """
    ingore_keywords = configs.get("ignore_tree_alert_keywords", [])
    if not ingore_keywords:
        return servers
    if not isinstance(ingore_keywords, str):
        return servers
    ingore_keywords_list = ingore_keywords.split(",,,")
    if not ingore_keywords_list:
        return servers
    return [server for server in servers if not any(keyword in server.name for keyword in ingore_keywords_list)]


def get_unbound_servers(session):
    """
    获取未绑定服务树的服务器
    :param session: 数据库会话
    :return: 未绑定服务树的服务器列表
    """
    tree_asset_ids = session.query(TreeAssetModels.asset_id).filter(TreeAssetModels.asset_type == "server").all()
    tree_asset_ids = [item[0] for item in tree_asset_ids]

    servers = (
        session.query(AssetServerModels)
        .filter(
            AssetServerModels.state == "运行中",
            AssetServerModels.is_expired.is_(False),
            AssetServerModels.id.notin_(tree_asset_ids),
        )
        .all()
    )

    # 过滤掉不需要发送告警的服务器
    return filter_ingore_tree_alert_servers(servers)


def bind_server_tasks():
    """
    检查server是否绑定服务树, 如果未绑定则发送告警
    # todo: 抽象通知中心告警，发送不同类型的告警逻辑
    :return:
    """

    @deco(RedisLock("server_binding_tasks_redis_lock_key"))
    def index():
        logging.info("开始检查server是否绑定服务树！！！")
        with DBContext("w", None, True) as session:
            # 获取所有绑定服务树的server
            servers = get_unbound_servers(session)
            if servers:
                # 1. 归类（基于前10个字符）
                grouped_servers = defaultdict(list)
                for server in servers:
                    prefix = server.name[:10] if len(server.name) >= 10 else server.name  # 截取前10个字符
                    grouped_servers[prefix].append(server)

                # 2. 统计每个分组的数量
                group_counts = {k: len(v) for k, v in grouped_servers.items()}

                # 3. 取 Top 3 最大分组
                top_3_groups = Counter(group_counts).most_common(3)
                ready_to_send_servers = []
                for prefix, size in top_3_groups:
                    ready_to_send_servers += grouped_servers[prefix]

                # 4. 发送告警
                if ready_to_send_servers:
                    body = {
                        "alert_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "servers": "\n".join(
                            [f"【{server.name}|{server.inner_ip}】" for server in ready_to_send_servers]
                        ),
                        "title": "【CMDB】主机未绑定服务树",
                    }
                    send_router_alert(params={"cmdb_server_not_bind_tree": 1}, body=body)

            logging.info("检查server是否绑定服务树结束！！！")

    try:
        index()
    except Exception as err:
        logging.error(f"检查server是否绑定服务树出错 {str(err)}")


def get_asset_product_mapping() -> Dict[str, str]:
    """
    获取资产类型到云产品类型的映射
    """
    return {
        "server": "ECS",
        "lb": "CLB",
        "mongodb": "veDB for DocumentDB",
        "redis": "veDB_for_Redis",
        "mysql": "RDS for MySQL",
        "cluster": "VKE",
    }


def query_monthly_paid_instances(cloud_name: str, resource_type: str):
    """
    查询包年包月的实例
    """
    asset_model = asset_mapping.get(resource_type)
    if not asset_model:
        raise ValueError(f"资源类型 {resource_type} 不存在")

    with DBContext("w", None, False) as session:
        query = session.query(
            asset_model.region, asset_model.account_id, asset_model.instance_id, asset_model.ext_info
        ).filter(
            asset_model.is_expired.is_(False),
            asset_model.cloud_name == cloud_name,
        )
        # 如果模型有state字段，才加入state过滤条件
        if hasattr(asset_model, "state"):
            query = query.filter(asset_model.state == "运行中")
        instances = query.all()

    return instances


def filter_monthly_paid_instances(instances):
    """
    过滤包年包月的实例, 如果实例没有ext_info,
    """
    filtered_instances = []
    for instance in instances:
        if hasattr(instance, "ext_info") and instance.ext_info:
            if instance.ext_info.get("charge_type", "") == "包年包月":
                filtered_instances.append(instance)
        else:
            filtered_instances.append(instance)
    return filtered_instances


def group_instances_by_region_account(instances):
    """
    按地区和账户分组实例
    """
    region_instances = defaultdict(list)
    for region, account_id, instance_id, _ in instances:
        region_instances[(region, account_id)].append(instance_id)
    return region_instances


def execute_volc_auto_renew_inspection(cloud_name: str, resource_type: str, region_instances: dict) -> List:
    """
    执行火山云自动续费巡检
    """
    asset_product_mapping = get_asset_product_mapping()
    cloud_product_type = asset_product_mapping.get(resource_type)
    if not cloud_product_type:
        raise ValueError(f"未知的资产类型: {resource_type}")

    total_result = []

    # 遍历每个 region，分批处理
    for (region, account_id), instance_ids in region_instances.items():
        cloud_configs = get_cloud_config(cloud_name, account_id)
        if not cloud_configs:
            continue

        auto_renew_obj = VolCAutoRenew(
            access_id=cloud_configs[0]["access_id"],
            access_key=mc.my_decrypt(cloud_configs[0]["access_key"]),
            region=region,
            account_id=account_id,
        )

        batch_size = 100
        for i in range(0, len(instance_ids), batch_size):
            time.sleep(0.1)
            batch = instance_ids[i : i + batch_size]
            request = VolCAutoRenew.build_request(instance_ids=batch, product=cloud_product_type)
            _inspector = VolCAutoRenewInspector(instance_obj=auto_renew_obj, request=request)
            result = _inspector.run()

            if not result.data or not result.success:
                continue
            total_result.extend(result.data)

    return total_result


def send_volc_auto_renew_notification(resource_type: str, result: List):
    """
    发送火山云自动续费巡检通知
    """
    if not result:
        logging.info("巡检完成, 未发现开通包年包月未自动续费实例")
        return

    send_feishu_notification(
        message=f"火山云{resource_type}自动续费巡检结果",
        notify_configs=configs.billing_notify_configs,
        at_user=True,
        use_card=True,
        title=f"火山云{resource_type}自动续费巡检结果",
        instances=result,
    )


def volc_auto_renew_task_by_resource(cloud_name: str = "volc", resource_type: Optional[str] = None):
    """
    火山云自动续费巡检任务 - 协调器函数
    """
    assert resource_type is not None, "资源类型不允许为空"

    try:
        # 1. 查询实例
        instances = query_monthly_paid_instances(cloud_name, resource_type)
        if not instances:
            return

        # 2. 过滤包年包月实例
        filtered_instances = filter_monthly_paid_instances(instances)

        # 3. 分组
        region_instances = group_instances_by_region_account(filtered_instances)

        # 4. 执行巡检
        inspection_result = execute_volc_auto_renew_inspection(cloud_name, resource_type, region_instances)

        # 5. 发送通知
        send_volc_auto_renew_notification(resource_type, inspection_result)

    except Exception as e:
        logging.error(f"火山云{resource_type}自动续费巡检任务执行失败: {str(e)}")
        raise
    else:
        logging.info(f"火山云{resource_type}自动续费巡检任务执行成功")


def volc_auto_renew_task():
    """
    火山云自动续费巡检任务
    """

    @deco(RedisLock("volc_auto_renew_tasks_redis_lock_key"))
    def index():
        volc_auto_renew_task_by_resource(resource_type="server")  # 主机
        volc_auto_renew_task_by_resource(resource_type="lb")  # LB
        volc_auto_renew_task_by_resource(resource_type="mongodb")  # Mongo
        volc_auto_renew_task_by_resource(resource_type="redis")  # Redis
        volc_auto_renew_task_by_resource(resource_type="mysql")  # Mysql
        volc_auto_renew_task_by_resource(resource_type="cluster")  # k8s

    try:
        index()
    except Exception as err:
        logging.error(f"火山云自动续费巡检任务出错 {str(err)}")


def execute_qcloud_auto_renew_inspection(
    cloud_name: str, resource_type: str, instances: List
) -> Optional[InspectorResult]:
    """
    执行腾讯云自动续费巡检
    """
    if not instances:
        return None

    instances_objs = []
    for region, account_id, instance_id, ext_info in instances:
        instances_objs.append(dict(region=region, account_id=account_id, instance_id=instance_id, ext_info=ext_info))

    _inspector = QCloudAutoRenewInspector(instance_objs=instances_objs)
    result = _inspector.run()

    if not result.success:
        logging.error(f"腾讯云自动续费巡检任务出错 {result.message}")
        return None

    return result


def send_qcloud_auto_renew_notification(resource_type: str, result: InspectorResult):
    """
    发送腾讯云自动续费巡检通知
    """
    if not result or not result.data:
        logging.info("巡检完成, 未发现需要关注的自动续费实例")
        return

    at_user = result.status == InspectorStatus.EXCEPTION
    send_feishu_notification(
        message=f"腾讯云{resource_type}自动续费巡检结果",
        notify_configs=configs.billing_notify_configs,
        at_user=at_user,
        use_card=True,
        title=f"腾讯云{resource_type}自动续费巡检结果",
        instances=result.data,
    )


def qcloud_auto_renew_task_by_resource(cloud_name: str = "qcloud", resource_type: Optional[str] = None):
    """
    腾讯云自动续费巡检任务
    """
    assert resource_type is not None, "资源类型不允许为空"

    try:
        # 1. 查询实例
        instances = query_monthly_paid_instances(cloud_name, resource_type)
        if not instances:
            return

        # 2. 执行巡检
        result = execute_qcloud_auto_renew_inspection(cloud_name, resource_type, instances)

        # 3. 发送通知
        send_qcloud_auto_renew_notification(resource_type, result)

    except Exception as e:
        logging.error(f"腾讯云{resource_type}自动续费巡检任务执行失败: {str(e)}")
        raise
    else:
        logging.info(f"腾讯云{resource_type}自动续费巡检任务执行成功")


def qcloud_auto_renew_task():
    """
    腾讯云续费巡检任务
    """

    @deco(RedisLock("qcloud_auto_renew_tasks_redis_lock_key"))
    def index():
        qcloud_auto_renew_task_by_resource(resource_type="server")  # 主机
        qcloud_auto_renew_task_by_resource(resource_type="lb")  # LB
        qcloud_auto_renew_task_by_resource(resource_type="redis")  # Redis
        qcloud_auto_renew_task_by_resource(resource_type="mongodb")  # Mongo
        qcloud_auto_renew_task_by_resource(resource_type="mysql")  # Mysql

    try:
        index()
    except Exception as err:
        logging.error(f"腾讯云续费巡检任务出错 {str(err)}")


def send_feishu_notification(
    message: str,
    notify_configs: List[dict],
    at_user: bool = False,
    use_card: bool = False,
    title: Optional[str] = None,
    instances: List[Dict[str, any]] = None,
) -> None:
    """
    发送飞书通知
    :param message: 消息内容
    :param notify_configs: 通知配置列表
    :param at_user: 是否@用户
    :param use_card: 是否使用卡片消息
    :param title: 卡片标题
    :param instances: 实例列表
    """
    for notify_config in notify_configs:
        if notify_config.get("type") != "feishu":
            continue

        webhook_url = notify_config.get("webhook_url")
        if not webhook_url:
            logging.warning("飞书webhook_url为空，跳过发送")
            continue

        try:
            bot = FeishuBot(webhook_url=webhook_url)

            if use_card:
                # 发送卡片消息
                if not title or not instances:
                    logging.warning("卡片消息缺少必要参数(title或instances)，跳过发送")
                    continue
                bot.send_instance_message(title=title, instances=instances)
                logging.info(f"飞书卡片通知发送成功: {title}, 实例数量: {len(instances)}")
            else:
                # 发送文本消息
                final_message = message
                if at_user and notify_config.get("user_id"):
                    final_message = f'<at user_id="{notify_config["user_id"]}"></at> {message}'

                bot.send_text_message(final_message)
                logging.info(f"飞书文本通知发送成功: {final_message}")

        except Exception as e:
            logging.error(f"发送飞书通知失败: {e}")


def volc_billing_task(cloud_name="volc"):
    """
    火山云账单巡检任务
    """
    logging.info("开始火山云账单巡检任务")
    cloud_settings = get_cloud_config(cloud_name)
    for cloud_setting in cloud_settings:
        billing_obj = VolCBilling(
            access_id=cloud_setting["access_id"],
            access_key=mc.my_decrypt(cloud_setting["access_key"]),
            region=cloud_setting["region"],
            account_id=cloud_setting["account_id"],
        )
        billing_inspector = VolCBillingInspector(
            instance_obj=billing_obj,
            threshold=configs.get("volc_billing_threshold"),
        )
        result = billing_inspector.run()
        if not result.success:
            # 巡检异常
            logging.error(f"火山云账单巡检异常 {result.message}")
            return
        at_user = result.status == InspectorStatus.EXCEPTION
        send_feishu_notification(result.message, configs.billing_notify_configs, at_user)

    logging.info("火山云账户巡检任务结束")


def qcloud_billing_task():
    """
    腾讯云账单巡检任务
    """
    logging.info("开始腾讯云账单巡检任务")
    cloud_settings = get_cloud_config("qcloud")
    for cloud_setting in cloud_settings:
        region = cloud_setting["region"]
        # 任意region
        if "," in region:
            region = region.split(",")[0]
        billing_obj = QCloudBilling(
            access_id=cloud_setting["access_id"],
            access_key=mc.my_decrypt(cloud_setting["access_key"]),
            region=region,
            account_id=cloud_setting["account_id"],
        )
        billing_inspector = QCloudBillingInspector(
            instance_obj=billing_obj,
            threshold=configs.get("qcloud_billing_threshold"),
        )
        result = billing_inspector.run()
        at_user = result.status == InspectorStatus.EXCEPTION
        send_feishu_notification(result.message, configs.billing_notify_configs, at_user)
    logging.info("腾讯云账户巡检任务结束")


def billing_tasks():
    """
    账单巡检任务
    """

    @deco(RedisLock("billing_tasks_redis_lock_key"))
    def index():
        volc_billing_task()
        qcloud_billing_task()

    try:
        index()
    except Exception as err:
        logging.error(f"账户巡检任务出错 {str(err)}")


def init_scheduled_tasks():
    """
    初始化定时任务
    """
    scheduler.add_job(
        notify_unbound_agents_tasks,
        "cron",
        hour="9-23",
        minute=0,
        id="notify_unbound_agents_tasks",
    )
    scheduler.add_job(bind_agent_tasks, "cron", minute="*/3", id="bind_agents_tasks", max_instances=1)
    scheduler.add_job(bind_server_tasks, "cron", hour=10, minute=0, id="bind_server_tasks", max_instances=1)
    scheduler.add_job(volc_auto_renew_task, "cron", hour=9, minute=30, id="volc_auto_renew_task", max_instances=1)
    scheduler.add_job(qcloud_auto_renew_task, "cron", hour=9, minute=30, id="qcloud_auto_renew_task", max_instances=1)
    scheduler.add_job(billing_tasks, "cron", hour=10, minute=0, id="billing_tasks", max_instances=1)


if __name__ == "__main__":
    pass

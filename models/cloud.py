#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Contact : 191715030@qq.com
Author  : shenshuo
Date    : 2023/2/15 14:59
Desc    : 云配置
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from models.base import TimeBaseModel

Base = declarative_base()


class CloudSettingModels(TimeBaseModel):
    __tablename__ = 't_cloud_settings'  # 云账户配置信息
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column('account_id', String(100), unique=True, nullable=False,
                        comment='AccountUUID')  # 云厂商ID,UUID
    name = Column('name', String(120), nullable=False, comment='名称')
    cloud_name = Column('cloud_name', String(120), nullable=False, comment='云厂商Name')  # aliyun / qcloud /aws
    project_id = Column('project_id', String(120), default='', comment='项目ID，用来标识您的项目的唯一字符串')
    region = Column('region', String(500), nullable=False, comment='区域')
    access_id = Column('access_id', String(120), nullable=False, comment='IAM角色访问密钥')
    access_key = Column('access_key', String(255), nullable=False, comment='IAM角色访问密钥')
    account_file = Column('account_file', Text(), comment='IAM角色访问密钥文件')
    is_enable = Column('is_enable', Boolean(), default=False, comment='是否开启')
    interval = Column(Integer, nullable=False, default=30, comment='同步间隔(单位：minutes)')
    detail = Column('detail', Text(), comment='备注')


class SyncLogModels(Base):
    __tablename__ = 't_sync_log'  # server 资产同步Log
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column('name', String(120), nullable=False, comment='名称')
    cloud_name = Column('cloud_name', String(120), nullable=False, comment='云厂商Name')
    account_id = Column('account_id', String(120), nullable=False, index=True, comment='AccountUUID')
    sync_type = Column('sync_type', String(120), comment='主机or数据库')
    sync_region = Column('sync_region', String(120), comment='区域')
    sync_state = Column('sync_state', String(120), comment='同步状态')
    sync_consum = Column('sync_consum', String(120), comment='同步耗时')
    sync_time = Column('sync_time', DateTime(), default=datetime.now, index=True, comment='同步时间')
    loginfo = Column('loginfo', Text(), comment='log')


class CloudBillingSettingModels(Base):
    __tablename__ = 't_cloud_billing_settings' # 云账户账单巡检配置信息
    id = Column(Integer, primary_key=True, autoincrement=True)
    threshold =  Column('threshold', String(120), nullable=False, comment='余额阈值')
    scheduled_expr = Column(String(64), nullable=False, default='0 10 * * *', comment='巡检调度表达式，默认为每天10点')
    cloud_setting_id = Column('cloud_setting_id', String(120), nullable=False, index=True, comment='云账户配置id')
    webhook_type = Column('webhook_type', String(120), nullable=False, comment='webhook类型')
    webhook_url = Column('webhook_url', Text(), comment='webhook地址', nullable=False)
    webhook_secret = Column('webhook_secret', Text(), comment='webhook签名密钥', nullable=True)
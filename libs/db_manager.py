# -*- coding: utf-8 -*-
# @Author: Dongdong Liu
# @Date: 2025/11/7
# @Description: Description

from urllib.parse import quote_plus
from sqlalchemy import create_engine
from websdk2.consts import const
from websdk2.configs import configs


class DBEngineManager:
    """数据库引擎管理类：支持多库、自动初始化与缓存"""

    def __init__(self, settings: dict = None):
        self._settings = settings or configs
        self._engines = {}
        self._initialized = False

    def init_engines(self):
        """初始化所有数据库引擎"""
        databases = self._settings.get(const.DB_CONFIG_ITEM, {})
        for dbkey, db_conf in databases.items():
            dbuser = db_conf.get(const.DBUSER_KEY)
            dbpwd = db_conf.get(const.DBPWD_KEY)
            dbhost = db_conf.get(const.DBHOST_KEY)
            dbport = db_conf.get(const.DBPORT_KEY)
            dbname = db_conf.get(const.DBNAME_KEY)

            url = (
                f"mysql+pymysql://{dbuser}:{quote_plus(dbpwd)}@"
                f"{dbhost}:{dbport}/{dbname}?charset=utf8mb4"
            )

            engine = create_engine(
                url,
                logging_name=dbkey,
                pool_size=10,
                max_overflow=50,
                pool_recycle=3600,
                pool_pre_ping=True,
                pool_timeout=60,
            )

            self._engines[dbkey] = engine

        self._initialized = True

    def get_engine(self, dbkey: str = 'default'):
        """获取指定数据库引擎"""
        if not self._initialized:
            self.init_engines()
        if dbkey not in self._engines:
            raise KeyError(f"Database key '{dbkey}' not found in configuration")
        return self._engines[dbkey]

    def dispose_all(self):
        """关闭并释放所有连接池"""
        for key, engine in self._engines.items():
            engine.dispose()
        self._engines.clear()
        self._initialized = False


db_manager = DBEngineManager()
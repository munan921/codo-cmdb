#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File    :   base.py
# @Time    :   2025/06/04 15:49:06
# @Author  :   DongdongLiu
# @Version :   1.0
# @Desc    :   巡检基类

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class InspectorStatus(Enum):
    """
    巡检状态枚举
    """

    NORMAL = "normal"  # 正常
    EXCEPTION = "exception"  # 异常


@dataclass
class InspectorResult:
    """
    巡检结果
    """

    status: InspectorStatus
    success: bool
    message: str
    data: Optional[Any] = None


class BaseInspector(ABC):
    """
    巡检类
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run(self) -> InspectorResult:
        """
        执行巡检逻辑，需返回结构化结果
        :return:
        """
        pass

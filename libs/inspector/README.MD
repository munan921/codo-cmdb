# 云厂商自动巡检入口, 提供定时任务调用
├── __init__.py
├── qcloud
│ ├── __init__.py
│ ├── auto_renew.py # 腾讯云自动付费巡检
│ └── billing.py    # 腾讯云账单巡检
└── volc
    ├── __init__.py
    ├── auto_renew.py # 火山云自动付费巡检
    └── billing.py    # 火山云账单巡检
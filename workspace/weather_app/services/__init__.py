"""services —— 业务服务层。

weather_service 组合「在线 provider」与「离线 provider」，
提供缓存与「在线失败自动降级」能力，是界面层唯一需要依赖的业务入口。
services 层可依赖 providers 与 core，但不得依赖 ui。
"""

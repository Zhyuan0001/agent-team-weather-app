"""core —— 纯逻辑层。

本层只包含与界面、网络无关的纯函数与数据结构：
    models      天气记录数据结构与天气状况常量
    errors      自定义异常
    date_utils  日期解析与范围校验（日期处理的唯一入口）
    units       摄氏/华氏换算与温度格式化
    formatting  天气状况 -> 中文名/emoji 的展示映射

约束：本层严禁 import PyQt5 或 requests。
"""

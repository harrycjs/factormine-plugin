"""
common — factormine-plugin 公共回测库

模块：
- data_loader: 加载本地 parquet（兼容 share_stock_* 与 ashare_stock_* 双前缀）
- factor_utils: 因子预处理（winsorize / standardize / neutralize_factor）
- factor_eval: 评估指标（IC / ICIR / 分组回测 / 多空组合 / 换手 / OOS）

所有函数均接受 DataFrame 为主入参，不读 parquet 直 IO（除 data_loader），
保持纯函数风格便于单测。
"""
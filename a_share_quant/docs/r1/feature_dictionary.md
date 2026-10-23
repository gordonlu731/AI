# R1 独立特征与结果字段

所有特征在 t 收盘生成，只读本连续数据段截至 t 的已完成日线。`anchor_features.csv.gz` 保存全部锚点、全部方法的分项；`all_daily_states.jsonl.gz` 保存非锚点、无信号、预热与缺口状态。R0 core 没有修改。

| 字段/组 | 解释与单位 | 缺失含义 |
|---|---|---|
| up/down_abs_return | 最近确认同方向段的算术幅度绝对值 | 无已确认同方向段 |
| up/down_duration | 极值间连续观测交易日数，确认日另存 | 同上 |
| up/down_speed | 幅度绝对值 / 持续日数 | 同上 |
| up/down_relative_volume | 波段每一天量 / 当天以前 20 日均量，再取平均 | 无完整前量窗口；不倒填 |
| up/down_efficiency | 幅度绝对值 / 平均相对量 | 没有可用相对量 |
| retracement | 最近确认下跌幅度 / 其之前确认上涨幅度 | 无配对段 |
| drawdown20 / rebound20 | 当前收盘距过去 20 日最高/最低收盘的比例 | 数据段不足时只用于诊断，建模须 120 日预热 |
| center_damage / lower_damage | 收盘低于参考中枢重心/下沿的比例，未破坏为 0 | 无当前有效参考中枢，不写成 0 |
| close_to_centroid / band_width | 相对重心距离 / 区间宽度比例 | 无有效中枢 |
| lower_wick / upper_wick | 影线 / 当日完整价格范围 | 平 K 为 0 |
| close_location | (C-L)/(H-L)，0 为低收，1 为高收 | 平 K 定义为 0.5 |
| breach_age | 参考中枢发生未收复收盘破位已过日数 | 未破位或已收复 |
| reclaim_sessions / fraction | 破下沿至收盘回到重心的已观察用时 / 收复收盘相对下沿涨幅 | 未观察到收复，不推断未来 |
| up/down_size/speed/volume_change | 最新同向段指标 / 前一同向段指标 | 没有前段或分母为零 |
| up/down_last_three | 最近三轮同方向段的幅度、日数、速度、相对量、效率原始分项 | 轮数不足则短列表；不纳入线性模型的嵌套字段 |
| zone_present/age/tests/flips | 参考中枢存在、确认后年龄、独立测试数、角色转换次数 | 无参考区间时对应数值为 null，presence=0 |
| recent_invalidations | 过去 20 日失效/到期的中枢数 | 0 是观察到没有，不代表不会失效 |
| bottom_shape/depth/first_rebound/second_low_difference/confirmation_age | 确认二底结构标记、第一底此前 120 日跌幅、首次反弹、两低点差、确认后年龄 | 未有已确认低高低时保存 null 与阶段原因 |
| momentum20 / atr_fraction / benchmark_momentum20 | 简单基线：20 日动量、14 日 ATR/收盘、同期指数动量 | 输入不可用时训练期规则填补并增加缺失标记 |
| lower/upper_distance | 当时路径上下边界距收盘的比例，仅用于解释不同区间几何 | 无合法边界；不把不同距离的触及概率直接排名 |

`FeatureGroups` 是预注册的九个独立特征组，不是投资分数。逐组加入简单基线、完整模型逐组删除以及 H3 相对跌幅/反弹基线的结果全部保存。组内特征有数学相关性，回归对照不是因果贡献证明；本实验没有手工综合权重。

中枢完整价格范围、重心、日期、角色和测试明细保存在本地 `snapshot-price-details.json`，不会把供应商价格上传公开仓库。形成日期与确认日期分开。R0/ATR 中枢 members 是独立波段 ID，密集区/承接区 members 是实际观测行索引。

结果 `return` 是复权口径的毛比例，`net_return` 使用假设每边 10bp，`excess_return` 为净比例减同期上证综指价格指数比例；不等于账户收益或严格总收益超额。MAE/MFE 包含入场日、上下方向以 0 截断；`path_drawdown` 用开盘入场后每日收盘路径计算。

路径标签 upper_first/lower_first/ambiguous/neither/missing_barriers 互相区分。日开盘已越界可以确定先触及该边；若开盘在两界内且当日高低均触及，记 ambiguous。预测二分类仅比较明确先触及上/下界的样本，其他状态的数量必须一起看。

所有行业字段为 unavailable；没有历史行业证据，不用当前分类回填。每个市场时间块为 20 个日历代理交易日，同股锚点最多 20 日持有，双向聚类重采样处理股票与同期市场依赖。六只现存股票不是全市场随机样本。

# 精华制药 2026 年 9–10 月｜已知案例，不计入盲测评分

数据截至 2026-10-23；10 月尚未结束，不包含其后行情。使用新增单股快照，未覆盖 R1 冻结数据。
本次没有改参数、没有新增模型拟合、没有计算或解封独立测试集结果。各截点图只使用当时及以前行情。
本期日线 33 根；两接口近期核验结果见审计，历史时点版本/停牌/ST/涨跌停/可成交性仍未核验。
满足原有 20 日价突破与 1.5 倍量条件的日期：2026-09-01、2026-09-09
R0 趋势通过并发出信号 1 日；底部 0 日。它们只是冻结规则的结果，不代表可成交买点。
以下为机械结构记录，不把区间当成已证实支撑/压力；R0 legacy 的 valid 只是原逻辑保留，不能等同有效性已核验。

## 截点 2026-09-01
r0_legacy：保留/有效 21 个，失效/到期 0 个；最新参考角色 both、年龄 17，下沿破坏比例 0.00%。
atr_intersection：保留/有效 1 个，失效/到期 21 个；最新参考角色 support、年龄 6，下沿破坏比例 0.00%。
density：保留/有效 3 个，失效/到期 84 个；最新参考角色 support、年龄 3，下沿破坏比例 0.00%。
support：保留/有效 1 个，失效/到期 25 个；最新参考角色 support、年龄 17，下沿破坏比例 0.00%。
R0 趋势拒绝：highs_not_rising、pullback_outside_range、up_energy_insufficient
R0 底部拒绝：not_deep_decline、retest_outside_band、selling_not_decaying

## 截点 2026-09-15
r0_legacy：保留/有效 22 个，失效/到期 0 个；最新参考角色 both、年龄 1，下沿破坏比例 0.00%。
atr_intersection：保留/有效 1 个，失效/到期 21 个；最新参考角色 support、年龄 16，下沿破坏比例 0.00%。
density：保留/有效 3 个，失效/到期 84 个；最新参考角色 support、年龄 13，下沿破坏比例 0.00%。
support：保留/有效 1 个，失效/到期 25 个；最新参考角色 support、年龄 27，下沿破坏比例 0.00%。
R0 趋势拒绝：rr_below_min
R0 底部拒绝：rr_below_min、not_deep_decline、selling_not_decaying、recovery_not_confirmed

## 截点 2026-09-30
r0_legacy：保留/有效 22 个，失效/到期 0 个；最新参考角色 both、年龄 11，下沿破坏比例 0.00%。
atr_intersection：保留/有效 1 个，失效/到期 21 个；最新参考角色 support、年龄 26，下沿破坏比例 0.00%。
density：保留/有效 2 个，失效/到期 85 个；最新参考角色 support、年龄 23，下沿破坏比例 0.00%。
support：保留/有效 2 个，失效/到期 25 个；最新参考角色 support、年龄 6，下沿破坏比例 0.00%。
R0 趋势拒绝：rr_below_min、lows_not_rising、highs_not_rising
R0 底部拒绝：rr_below_min、not_deep_decline、weak_first_rebound

## 截点 2026-10-15
r0_legacy：保留/有效 22 个，失效/到期 0 个；最新参考角色 both、年龄 17，下沿破坏比例 1.37%。
atr_intersection：保留/有效 2 个，失效/到期 21 个；最新参考角色 support、年龄 4，下沿破坏比例 0.25%。
density：保留/有效 2 个，失效/到期 85 个；最新参考角色 support、年龄 29，下沿破坏比例 0.00%。
support：保留/有效 2 个，失效/到期 25 个；最新参考角色 support、年龄 12，下沿破坏比例 0.00%。
R0 趋势拒绝：rr_below_min、lows_not_rising、up_energy_insufficient、latest_low_broken
R0 底部拒绝：rr_below_min、unconfirmed_bottom_sequence、not_deep_decline、weak_first_rebound、retest_outside_band、selling_not_decaying、recovery_not_confirmed

## 截点 2026-10-23
r0_legacy：保留/有效 22 个，失效/到期 0 个；最新参考角色 both、年龄 23，下沿破坏比例 7.37%。
atr_intersection：保留/有效 2 个，失效/到期 21 个；最新参考角色 resistance、年龄 10，下沿破坏比例 6.31%。
density：保留/有效 2 个，失效/到期 85 个；最新参考角色 support、年龄 35，下沿破坏比例 0.00%。
support：保留/有效 2 个，失效/到期 25 个；最新参考角色 resistance、年龄 18，下沿破坏比例 5.37%。
R0 趋势拒绝：rr_below_min、lows_not_rising、pullback_outside_range、up_energy_insufficient、latest_low_broken
R0 底部拒绝：rr_below_min、unconfirmed_bottom_sequence、not_deep_decline、weak_first_rebound、retest_outside_band、selling_not_decaying、recovery_not_confirmed

## 判读边界
中枢为空、区域过宽、陈旧区间保留、角色转换和确认延迟均保留在逐日记录中，没有为本案例修改阈值。
本报告不根据后续收益评价算法优劣；与首批匿名图分开，建议先独立完成匿名标注再阅读本已知案例。
新旧快照重叠期不同的日期数：0。不同则保留两份来源，不自动拼接或修复。

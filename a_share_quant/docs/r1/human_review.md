# 真实人工评审操作

当前没有已完成的人工评审。`human_agreement.json` 的 pending 与空误差列表不是零错误，也不是算法已通过验收。

1. 向评审者只提供 `r1-blind-review.zip`。不提供 PRIVATE-unblinding-key、指定案例图、预注册股票/日期映射或未来收益。评审者若主动查阅公开源码/种子仍可能重建映射；这是流程盲法，不宣称不可破解。
2. 先看 Bxxx-blank.png，在 `human_regions_template.csv` 中填写本人认为存在的中枢下沿、上沿和重心。坐标为图上的首可见收盘=100 的统一尺度。多中枢复制该 case_id 多行；明确无中枢则 reviewed=yes、no_center=yes，价格坐标留空。尚未评审保持 reviewed=no。
3. 再看 Bxxx.png 的 A–D 算法结果，在 `algorithm_judgments_template.csv` 填 correct/too_high/too_low/omission/false_detection，分别对应正确、偏高、偏低、遗漏、误识别，并写备注。图为可读性最多画最近四个区间；标题保留全部有效数。完整掩码价格区域另附 algorithm_regions.csv，数量审查应核对全量区域，不能把“图显示四个”当成“算法只输出四个”。
4. 将真实人工表保存为新文件，不覆盖模板。评分工具输出位置差、区间 IoU、ATR 归一重心差、数量差及漏检/多检，保留所有人工错误记录，不用于根据未来收益选择算法。

```bash
python research/r1/score_review.py \
  --human-regions reports/local/my-human-regions.csv \
  --algorithm-regions reports/local/r1-s1-structure-final/algorithm_regions.csv \
  --judgments reports/local/my-algorithm-judgments.csv \
  --output reports/local/my-review-results.json
```

匹配使用按掩码 ID 排序的确定性、正 IoU 贪心匹配；密集中枢多时可能不是最优匹配，需结合原表审查。没有人为区域时工具不生成假分数。人工偏高/偏低是评审标记，程序给出连续位置差作为补充。

当前机器审查已发现应重点人工检查的现象：密集区在高波动指定截点可能输出无中枢，承接区可能过宽，R0 可能保留很老的多个区域。它们是待审查警示，不冒充人工误识别结论。

# 真实人工评审操作

当前没有已完成的人工评审。`human_agreement.json` 的 pending 与空误差列表不是零错误，也不是算法已通过验收。

1. 首批只交付 `batch1-human-only.zip`，顺序 B001 → B002 → B003 → B004 → B005 → B006，严格复用原 12 组前六组，不重抽。**旧 `r1-blind-review.zip` 同时含算法图，不再作为首次材料。**不交付 PRIVATE-unblinding-key、指定案例图、预注册股票/日期映射或未来收益。评审者若主动查阅公开源码/种子仍可能重建映射；这是流程盲法，不宣称不可破解。
2. 看六张匿名 PNG / 六页 PDF，上窗完整历史、下窗最后 60 根放大；每张 2160×3360。复用原截点与连续行情段，最多 180 根，无算法叠加。K001 是窗口内首根，P 是首根收盘=100 的归一坐标，放大窗不重置坐标。成交量仅作日 K 相对量展示，不解释主动买卖盘。
3. 可用手机截图画多个框，写中枢1/2、底部1/2；也可用离线 `手机标注.html` 拖框、手填 K/P、选择没有/不确定并导出 JSON。人工重心可留空。多独立区域逐条记录，未填仍为 unreviewed。底部判断可稍后补充。不向服务器上传，草稿保存受浏览器限制，完成后主动导出。
4. 收到真实标注后，先在忽略目录保存原件、UTC 接收时间与 SHA256，按 case_id 固定版本；只揭示已审阅样本的 R0、ATR、密集区、承接区结果。未审阅样本继续隐藏，包括 B007–B012。若只收到底部标记，中枢仍 pending；不确定区域保留，不强行当成没有中枢评分。截图坐标含糊时保留原图及 uncertainty，不猜精确数值。
5. 复核新旧图的首可见日期/归一锚点一致，再进行可比字段评分。手机 CSV/JSON 不是旧评分器格式，不可直接传入。中心区域与底部区域分开；底部不与中枢算法强行匹配。人工没有填重心则重心误差 unavailable，不能代入几何中点。旧评分器只用于具有人工重心、或明确 no_center 的完整记录；部分区间可另报告区间交集/数量差，暂缺结果保留 pending。
6. 再对已揭示的 A–D 算法，在 `algorithm_judgments_template.csv` 填 correct/too_high/too_low/omission/false_detection，分别对应正确、偏高、偏低、遗漏、误识别，并写备注。图为可读性最多画最近四个区间；标题保留全部有效数。完整掩码价格区域另附 algorithm_regions.csv，数量审查应核对全量区域，不能把“图显示四个”当成“算法只输出四个”。
7. 将真实人工表保存为新文件，不覆盖模板。评分工具输出位置差、区间 IoU、ATR 归一重心差、数量差及漏检/多检，保留所有人工错误记录，不用于根据未来收益选择算法。算法揭示后的修订要保留原始盲评和修订原因，不能倒写首轮判断。

```bash
python research/r1/score_review.py \
  --human-regions reports/local/my-human-regions.csv \
  --algorithm-regions reports/local/r1-s1-structure-final/algorithm_regions.csv \
  --judgments reports/local/my-algorithm-judgments.csv \
  --output reports/local/my-review-results.json
```

匹配使用按掩码 ID 排序的确定性、正 IoU 贪心匹配；密集中枢多时可能不是最优匹配，需结合原表审查。没有人为区域时工具不生成假分数。人工偏高/偏低是评审标记，程序给出连续位置差作为补充。

交付/复现命令、检查结果与单独已知案例见 [首批交付记录](../../reports/human_review_2026-10-24/README.md)。首轮看图不向评审者提前提示任何具体案例的机器审查现象。

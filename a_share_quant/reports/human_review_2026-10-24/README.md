# R1 真实人工看图｜第一批交付记录

本轮仅调整展示和人工采集流程。R0/R1 源算法、预注册参数、样本抽取和既有统计结果冻结于 `cceef64bd72883aa82f5c4ca3a60acddf3787b92`，不合并 PR #2，不解封独立测试。

## 给评审者的第一阶段材料

- 原预注册 12 组的前六组：B001、B002、B003、B004、B005、B006，顺序固定；没有按图形或收益挑选。B007–B012 暂不展示。
- 六张 2160×3360 竖版 PNG、六页高清 PDF、含图的单文件离线 HTML、空白 CSV 与使用说明。全窗口最多 180 根，另放大最后 60 根；遇缺口只取原连续段，不填补、不替换截点。
- 只含截至原截点的匿名日 K 与相对量，无公司名称/代码、真实日期、算法线、未来收益或图形解读。横轴 K 是可见根序号，纵轴 P 为第一根收盘=100。两窗单位一致，各自纵轴范围可能不同。
- 首选在 Cloud 会话直接展示 PNG；可截图画多个中枢框、底部框并回传。也可下载离线 HTML 拖框/手填，选择没有明确中枢/不确定，导出 JSON 或 CSV。HTML 没有网络请求；本机草稿不能代替主动导出。
- 云端文件链接取决于客户端是否支持，**本地路径不是公开下载 URL**。无法打开附件时，用会话图片截图或 K/P 文字坐标反馈，不依赖本地 HTML。未建立公开行情下载站点。

文字模板（只有占位符，不是答案）：

```text
B001：
中枢1：K起–K止，P下–P上，人工重心（可空）
中枢2：……
底部1：K起–K止，P下–P上
或：没有明确中枢 / 判断不确定
备注：……
```

本地交付根目录为 `reports/local/mobile-review-2026-10-24/`。`batch1-human-only/` 和同名 ZIP 可交付；`private-audit/` 包含映射和合成浏览器测试，禁止混入。旧的 `r1-blind-review.zip` 已含算法图，禁止用于第一阶段。

## 收到标注后的第二阶段

首批交付时真实人工标注 **0**，随后 B001 完成；现已收到完整累计文件，首批首次盲标 **6/6**，新增五张，B001 未变。见 [六张汇总](first-six-v1/README.md)、[结构分歧](first-six-v1/observations.md) 和 [当前状态](review_status.json)。算法正确性判断仍等待真实反馈，不能把位置重叠当作已通过验收。后六组继续未展示，既有 B001 记录是历史阶段。

按 [人工操作规范](../../docs/r1/human_review.md) 保存原件与修订，逐样本核验完成状态后才揭示 R0、ATR、密集区、承接区结果。未评审样本不提前揭示。中心和底部区域分别保留；未填、没有、不确定严格区分。首轮缺少人工重心时重心误差 unavailable，禁止用几何中点填造。没有真实输入时不运行评分，不制造“通过”。原算法图最多显示四个区间，后续审阅同时核对全量掩码区域，保留遗漏/偏高/偏低/误识别。

## 已知案例，单独文件

精华制药 2026-09-01 至 2026-10-23 的结构诊断已单独完成，含 33 根当期日线记录、五个事前固定截点的四算法图、R0 逐项拒绝。10 月尚未结束，不补造其余日期。使用新增单股供应商快照，不替换 R1 冻结数据；同源两个接口近期重叠 1,023 根一致，新旧快照 9–10 月重叠差异 0。

价格图、完整坐标和 PDF 位于本地 `known-case-separate/`，不在盲包里。去直接价格的 [诊断报告](known_case/known_case_report.md)、[逐日派生记录](known_case/daily_diagnosis.json) 和 [来源审计](known_case/audit.json) 保存到 Git。建议先独立做匿名标注，再阅读已知案例，避免引导结构判断；不计入盲评评分，也未用后续收益评优。

行情仍为未验证历史时点的供应商快照；同源一致性不等于独立源/PIT/可成交性核验。本轮没有模型拟合、收益实验、参数搜索或解封测试，不声称新的投资结论。

## 验证与复现

本地 52 项 unittest 全部通过（原 47 + 5 项图表时间边界），包括原策略前缀不变性。编译、CLI 帮助/行情验证、JS 语法检查通过。盲包扫描、原顺序/截止点与文件校验通过。412×915、触屏/DPR 2.625 的 Chromium Android 模拟检查了拖框、多区域、空重心、无中枢、完成标记及 JSON 导出；实体 Android 尚未测试。

浏览器输入全是 **synthetic UI test**，导出只在 private-audit，不进入真实人工数据。初次浏览器启动受环境限制，之后 file:// 导航被托管浏览器策略阻止；改为仅在本机回环地址临时提供文件，测试后关闭，无公网托管。这些交付测试失败均保留，不属于策略实验。

```bash
cd a_share_quant
python -m pip install -e '.[review-check]'
# 另需 /usr/bin/chromium 和 Noto Sans CJK；生成器不下载行情。
python research/r1/mobile_review.py \
  --output reports/local/NEW-mobile-review/batch1-human-only \
  --audit reports/local/NEW-mobile-review/private-audit
python research/r1/check_mobile_review.py \
  --packet reports/local/NEW-mobile-review/batch1-human-only \
  --audit reports/local/NEW-mobile-review/private-audit
python -m unittest discover -s tests -v
python -m compileall -q src tests data/scripts research/r1
```

生成器依赖原冻结本地数据及 `reports/local/r1-s1-structure-final/PRIVATE-unblinding-key.json`，缺失则报错，不重抽/替代。输出目录必须为新目录，避免覆盖。离线 HTML 源模板在 [mobile_annotator.html](../../research/r1/mobile_annotator.html)，图表生成在 [mobile_review.py](../../research/r1/mobile_review.py)。本次中性清单、文件哈希及检查见本目录 JSON；源码与数据可分别核验，不公开价格包和映射。

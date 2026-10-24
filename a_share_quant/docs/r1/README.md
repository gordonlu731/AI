# R1 接续与复现

入口：[完整研究报告](../../reports/r1/R1-S1-report.md)、[预注册](../../research/r1/preregister.json)、[实验定义](experiment_spec.md)、[字段字典](feature_dictionary.md)、[人工评审](human_review.md)。R0 的算法和历史报告保持不变，R1 在 `quant-r1-structure-forces` 分支，PR 基于 `quant-research-foundation`，不自动合并。

## 环境与数据

以下均在 `a_share_quant/` 执行。核心结构/标签只用标准库；绘图和固定 ridge 实验需要可选环境：

```bash
python -m venv .venv-research
.venv-research/bin/python -m pip install -e '.[research]'
source .venv-research/bin/activate
python -m unittest discover -s tests -v
```

行情解码仍使用独立 `.venv-data` 和原有 `requirements-data.lock`，不改基础镜像或打印凭据。新环境无行情时，按原 README 获取两只案例股，然后逐只获取固定面板（已有输出会拒绝覆盖）：

```bash
for symbol in sz000001 sz000333 sz000858 sh600276 sh600900 sh601088
do
  .venv-data/bin/python data/scripts/fetch_sina.py --symbols "$symbol" \
    --end 2026-10-22 --output "data/processed/r1-panel/$symbol"
done
.venv-data/bin/python research/r1/prepare_benchmark.py
```

数据目录必须保持原契约和 manifest。原始快照不在 Git；新下载哈希不同只能称新快照实验，不能称逐字复现本轮供应商历史版本。2026 是本轮冻结截止日期，不是未来每次自动更新日期。

## 三阶段顺序

所有输出使用新目录，完成前两阶段再做增量实验：

```bash
python research/r1/structure_cases.py \
  --output reports/local/r1-repro-structure \
  --public reports/local/r1-repro-structure-derived

python research/r1/event_study.py \
  --structure-stage reports/local/r1-repro-structure-derived/structure_stage.json \
  --output reports/local/r1-repro-events-derived \
  --local reports/local/r1-repro-events-numeric

OPENBLAS_NUM_THREADS=1 python research/r1/incremental.py \
  --events reports/local/r1-repro-events-numeric \
  --event-audit reports/local/r1-repro-events-derived/event_audit.json \
  --output reports/local/r1-repro-models-derived
```

事件程序检查结构阶段标记和预注册哈希，独立 sealed_test 仅登记状态，收益标签不计算。边界 purge/embargo、数据缺口和无中枢都保留；不应为了得到正结果更改参数后覆盖本轮输出。

`report_tables.py` 从事件汇总、模型指标和本地数值标签生成小表/派生图；`publish.py` 的白名单只允许不含绝对价格的结果，超过 256 KiB 的 JSON 无损压为 `.json.gz`，保留原始与压缩 SHA256。例如：

```bash
python research/r1/publish.py \
  --source reports/local/r1-repro-events-derived \
  --output reports/r1/reproduction-events

python research/r1/package_figures.py \
  --figures reports/local/r1-repro-structure \
  --templates reports/local/r1-repro-structure-derived \
  --output reports/local/r1-repro-packets \
  --manifest reports/local/r1-repro-figure-manifest.json
```

图包和解盲文件始终在本地忽略目录，只有哈希清单可提交。盲评 ZIP 不含 PRIVATE-unblinding-key 或指定案例图；不要把完整结构目录误发给盲评者。

## 读取压缩结果与审计

```python
import gzip, json
with gzip.open('reports/r1/R1-S1-incremental/incremental_metrics.json.gz', 'rt') as f:
    metrics = json.load(f)
```

CSV 同理用 gzip.open 和 csv.DictReader。`publication_manifest.json` 的 source_sha256 对应解压字节，published_sha256 对应仓库文件；审计原文件名可能不带 .gz，这是无损发布格式映射，不是丢失文件。

已收到 B001 首轮真实手机标注并仅为该样本揭示四算法；B002–B006 仍未审阅。B001 空重心保持缺失，仅做区间与数量描述，算法正确/误识别的真人判断仍 pending，不用程序代填。最新状态见 [反馈记录](../../reports/human_review_2026-10-24/feedback-B001-v1/README.md)，原 R1 评分/报告文件保留历史状态，不覆盖。

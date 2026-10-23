# A 股价格结构量化研究

本项目研究持有 3–20 个交易日的上涨趋势回调与底部反转。当前版本 **R0 是新建研究基线**，未获得此前 ChatGPT 会话中的 V1–V4 文件，不能宣称延续其代码或效果。

**R1 独立实验**：新增因果结构、人工盲评模板、多空分项和封存验证研究，R0 保留原样。先读 [R1-S1 报告](reports/r1/R1-S1-report.md) 和 [R1 接续说明](docs/r1/README.md)。人工一致性仍待真实评审，投资假设未验证成立。

代码位于 `gordonlu731/AI` 仓库的 `quant-research-foundation` 分支、`a_share_quant/` 目录。原仓库其他分支是 Bellworks 项目，保持独立。若以后迁移至独立私有仓库，整个目录可直接搬迁。

建议按顺序阅读：

1. [策略定义与假设](strategy_spec.md)
2. [Codex 长期开发规范](AGENTS.md)
3. [研究日志](research_log.md)
4. [基础整理及首轮探索报告](reports/2026-10-23-foundation.md)
5. [后续开发路线](docs/roadmap.md) 与 [Cloud 接续说明](docs/cloud_setup.md)

## 本地与 Cloud 运行

核心只需 Python 3.11/3.12 标准库，不需要付费数据凭据或第三方测试框架。下列命令均在 `a_share_quant/` 中执行：

```bash
python -m venv .venv
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src tests data/scripts
PYTHONPATH=src .venv/bin/python -m ashare_quant --help
```

可选行情采集环境与核心隔离：

```bash
python -m venv .venv-data
.venv-data/bin/python -m pip install -r requirements-data.lock
.venv-data/bin/python data/scripts/fetch_sina.py \
  --end 2026-10-22 --output data/processed/sina-2026-10-22
```

输出目录已存在时会拒绝覆盖；复用相同截止日的原始响应缓存，换目录不会自动刷新供应商快照。需要新快照请使用新的截止日。接口可能限流/失效，错误和已完成原始响应保留在本地，不能伪造补全。

```bash
PYTHONPATH=src python -m ashare_quant validate \
  --bars data/processed/sina-2026-10-22/sz002349.csv \
  --manifest data/processed/sina-2026-10-22/sz002349.manifest.json \
  --calendar data/processed/sina-2026-10-22/calendar.csv

PYTHONPATH=src python -m ashare_quant research \
  --bars data/processed/sina-2026-10-22/sz002349.csv \
  --manifest data/processed/sina-2026-10-22/sz002349.manifest.json \
  --calendar data/processed/sina-2026-10-22/calendar.csv \
  --output reports/local/002349-r0-reproduction \
  --allow-snapshot-research
```

默认禁止用未核验因子/日历生成标签；显式探索开关只允许标注局限的事件研究，不会把数据升级为已核验。把代码中的 `sz002349` 换成 `sz300620` 可复现另一案例。`--params` 接受 `Parameters` 对应的 JSON，未给出的参数保持默认值；报告保存完整参数和源文件 SHA256。

## 输出与数据

- `run.json`：版本、代码提交/工作区状态/源文件哈希、参数、数据和日历校验和、数据缺口、限制。
- `assessments.jsonl`：所有预热完成后的判断，包括负例与冷却去重原因。
- `outcomes.jsonl`：每个发出信号对应的全部 3/5/10/20 日状态及收益/风险标签；失败与不可评估事件保留。
- `summary.json`：按策略与期限汇总，零样本指标为 null。
- `structures.json`：每个连续数据段的波段/中枢，索引为段内索引，同时保存全局段起点。

行情再分发许可尚未确认，真实原始行情、复权因子、价格图和完整本地结果不上传 GitHub。仓库保存获取脚本、数据契约、校验摘要、全部事件的非价格研究标签与结论。详见 [data/README.md](data/README.md)。合成行情只用于测试，不用于策略效果结论。

当前仅完成因果结构研究和探索性事件标签；没有可交易组合回测、样本外结论或下单功能。

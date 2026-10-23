# Codex Cloud 长期接续

## 已观察到的环境（2026-10-23）

- 当前 Cloud `/workspace` 最初没有项目检出文件，`.git` 占位目录不是 Git 仓库。项目后来检出至 `/workspace/AI`。
- Python 3.12.14、Git、gh 可用。核心测试使用标准库 unittest，不依赖当前镜像偶然已有的 pandas/numpy。
- `/etc/codex/network-policy.json` 显示启动 HTTP 策略 unrestricted，VPN 未配置。环境状态工具曾报告网络 policy state=unknown，不能把它当作 enforced。使用继承代理并启用工具的网络权限后 Git clone 和行情 HTTPS 请求成功；不关闭 TLS 或绕过代理。
- `gh` 的注入 token 在实际 API 请求返回 401 Bad credentials，无法用于推送。GitHub 连接器可读取该仓库并有 push 权限，本轮经连接器保存成果。未修改环境凭据或重登账号。
- 环境的 secret/runtime-variable/outbound-identity 列表为空；没有已核验付费行情凭据。

## 新会话接续步骤

在 Cloud 中选择 `gordonlu731/AI` 和 **`quant-research-foundation` 分支**，工作目录设为 `a_share_quant/`。只有合并 PR 后默认 main 才包含本项目；截至基础整理时不自动合并。

```bash
cd /workspace/AI/a_share_quant
python -m unittest discover -s tests -v
PYTHONPATH=src python -m ashare_quant --help
```

新容器不保证保留本轮虚拟环境与本地行情；按 README 重建。免费供应商当前快照也不保证逐字复现旧行情，因此仓库记录旧快照 SHA256，重新下载哈希不同时应创建新实验，不覆盖旧结论。

Cloud 环境配置界面可将“代码仓库/分支”“setup 命令”“工作目录”保存为长期环境设置。本轮能维护仓库，但没有更改该界面配置的工具，不能声称默认检出/凭据配置已永久修改。setup 可仅创建 `.venv` 并运行标准库测试；只在需要采集时安装 `requirements-data.lock`。

## ChatGPT / Work 读取入口

给具有 GitHub 权限的会话提供仓库链接，并明确分支与目录。优先阅读 README、strategy_spec.md、research_log.md、最新 reports 和 AGENTS.md。不存在读取此前聊天附件的隐式权限；历史 V1–V4 需要上传或作为真实文件提交后才能核查。

每次任务完成前保存策略与日志，检查无密钥/无未授权行情，提交到研究分支并更新 PR。不要只在聊天里记录实验。账户权限和仓库连接需要用实际读写结果核验，不把本地 `gh auth status` 或 UI 中“已连接”当作完成证据。

## 若改为独立仓库

建议私有 `a-share-quant`，Python 项目，默认 main，保留 PR 与 CI。当前 GitHub 连接器未提供创建仓库能力；需先创建并授权接入，再迁移 `a_share_quant/` 内容、提交历史与研究记录。当前做法继续利用已有 AI 仓库，不等待迁移即可工作。

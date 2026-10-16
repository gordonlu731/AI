# 第二轮 AI 物理预测测试：BW-PREDICT-002

**主持人指南，不要把本目录、评分包或整个代码仓库交给被测 AI。** 四个新场景使用独立实验配置，原首页和 src/machine.js、src/scene.js、src/main.js 均保留。A 包只有初始材料，B 包才包含实测结果。本指南不揭示各题答案。

## 两个下载包

- **Bellworks-Round2-AI-Input.zip：A 包，给被测 AI。** 解压后是 input/，含 7 张初始 PNG、场景说明、准确参数、提示词、空白答卷和哈希清单。
- **Bellworks-Round2-Operator-Kit.zip：B 包，自己留作评分。** 包含 A 的相同版本材料、独立评分脚本、真实运行记录、关键碰撞时间、结果截图和人工评分依据。只需 Node.js 22+，不需要 npm 安装或联网。

## 具体怎么问 AI

1. 在 GPT-6 高推理或希望测试的模型中，打开一个没有旧答案的新会话。记录模型、推理设置、日期、工具权限和是否看过相关答案。临时聊天不会出现在历史中，请及时保存原文。
2. **仅解压 A 包。** 上传其中的 7 张 PNG、SCENE.zh-CN.md、PHYSICS.json、RESPONSE_TEMPLATE.json，共 10 个附件。
3. 把 PROMPT.zh-CN.md 的全文复制为消息发送。MANIFEST.json 留作版本核对，不必上传。
4. 不提供 B 包、运行后的截图、仓库链接、开发聊天或第一轮评分说明。不允许联网搜索或执行仿真。
5. 保存第一次完整 JSON 答卷，再评分。可以把原始答卷发回维护项目的 Codex，由其锁定并核对。只修 JSON 格式时也要记录补问，不给结果提示。

如果只想补一句开场白：

> 请按照附件 PROMPT.zh-CN.md 完成第二轮物理预测，只用初始材料，不联网、不执行代码或物理仿真。按 RESPONSE_TEMPLATE.json 输出完整 JSON，不要声称已运行验证。

## 在 B 包中锁定与评分

解压 B 包，在其根目录打开终端，把原始答卷保存为 response.json：

```sh
node tools/freeze.mjs response.json --id trial-001 --model GPT-6 --reasoning high --session fresh-temporary-chat --exposure none --tools disabled
node tools/score.mjs operator/attempts/trial-001
```

`--exposure none` 和 `--tools disabled` 是主持人声明，脚本无法证明没有泄漏或工具使用。未知就填写 unknown。实际模型版本可用 --version 记录。原始预测、时间、哈希、模型元数据保存在 attempts/；评分不会覆盖已有结果。该目录被 Git 忽略，不会随正常 git add 提交。

评分沿用第一轮：撞钟 40 分、关键碰撞 36 分、阶段 24 分；概率另算 Brier。撞钟时间不计主分。解释和首次中断位置由人工核对，不用关键词自动评分。若任何场景的重复观测不稳定或原默认配置回归失败，会保留所有运行并禁止按单一确定标签评分。

## 实验页面与离线运行

原版首页仍是 `/`。独立第二轮页面是 `/round2.html`，可在五个初始配置 REF、Y1～Y4 间切换。释放前立即应用；运行中或暂停时的改动等 Reset 后应用。Start、Pause/Resume、Reset、速度和相机控制沿用原样式。不要让被测 AI 访问实验页面的运行结果。

成品 Bellworks.zip 中包含两个页面和本地全部运行资源。按项目中文 README 启动后，在原地址后添加 `round2.html`。开发者可用 `npm ci`、`npm run dev`、`npm run build`。所有运行资产都在本地，没有 CDN。

## 参数从哪里来

config/parameters.mjs 是四题固定的初始设置，config/experiments.mjs 在未释放的原 Machine 世界上仅改动对应碰撞体、骨牌或球密度。Y1 保持挡板底面，Y2 保持挡板高度和厚度，Y3 保持其余骨牌位置，Y4 同时重算质量与惯性。

PHYSICS.json 的五组对象和关节参数来自实际未运行的 Rapier 世界。轨道中心线来自同一个构造函数；轨道盒体规则、观测条件来自与源码哈希一致的第一轮初始几何说明。参数是程序设计值，不是照片估计或实物测量。截图均在时间 0、九个阶段均未触发时从真实浏览器拍摄。

operator/design-lock.json 在任何第二轮求解之前固定了数值和三份物理源文件的 SHA-256；其后不按结果调整。每次释放只改变球的固定/动态类型，之后没有电机、额外冲量、计时触发或按阶段回调推动机构。观测器只记录结果。

## 测试与重新采集

默认配置和四题各有三次全新世界、3600 步求解，以及三次生产构建浏览器验证。另有默认配置正常动画循环验证、五次最终接触诊断重放；完整通过情况见 B 包 operator/VALIDATION.md。第一轮数据和私人答卷未修改。

完整源码目录中的命令。浏览器采集需要另一个终端先启动 4192 端口服务：Windows CMD 先执行 `set PORT=4192`，PowerShell 先执行 `$env:PORT="4192"`，再执行 `node tools/serve.mjs`；Linux/macOS 可执行 `PORT=4192 node tools/serve.mjs`。

```sh
npm run build
# 采集工具默认端口 4192，也可用 TEST_URL 指定其他已启动的本地服务
node evaluation/round2/tools/export-input.mjs
node evaluation/round2/tools/capture-input.mjs
node evaluation/round2/tools/manifest.mjs
node evaluation/round2/tools/record-truth.mjs
node evaluation/round2/tools/inspect-outcomes.mjs
npm run test:round2:browser
node evaluation/round2/tools/replay-closeups.mjs
npm run test:round2
python3 evaluation/round2/tools/package.py
python3 evaluation/round2/tools/verify-packages.py
```

实测文件采用不覆盖写入，重复采集应新建协议和数据集目录，或先归档完整旧记录；不要覆盖已经用于模型预测的数据集。export-input 对相同设计保留原始锁定时间，不允许悄悄替换设计锁。修改输入截图或说明后也要重新生成清单和对应答案，已冻结预测不能跨版本评分。

本轮仍是四个有关联的图像＋参数题，不是只看图片的物理测试或通用基准。三次确定性重跑用于验证复现，不是三个独立题目。答案保存在可下载的 B 包和项目仓库中，盲测依赖被测模型没有访问它们；本地时间与哈希也不是可信第三方时间戳。

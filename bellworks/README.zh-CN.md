# The Bellworks：鲁布·戈德堡机械装置

[English](README.md) | **简体中文**

一个可以在浏览器中交互操作的九阶段三维机械装置。一颗钢球沿多层黄铜与木质轨道下降，通过真实碰撞驱动各个机构，最终推动击槌撞响悬挂的钟。

**Three.js 0.186.0 · Rapier 3D compat 0.20.0 · Vite · npm**

## 离线运行成品

1. 提前在电脑上安装 Node.js 22 LTS 或更新版本。
2. 从 GitHub 下载本目录中的 [Bellworks.zip](Bellworks.zip)：打开文件页面，点击 **Download raw file**，然后解压。
3. 保持解压目录中的 `dist/`、`tools/` 和 `start-offline.bat` 的相对位置不变。
4. Windows 用户双击 **`start-offline.bat`**；也可以在解压目录的终端中运行：

   ```sh
   node tools/serve.mjs
   ```

5. 在 Chrome 中打开 **http://127.0.0.1:4173**。

此方式**无需安装 npm 依赖，也无需联网**。`dist/` 已包含 Three.js、内嵌 WASM 的 Rapier、应用代码、样式和图标。材质、文字、环境光照和钟声均在本地生成。静态服务器仅使用 Node.js 内置模块，无第三方服务依赖。

运行时请保持终端打开；按 Ctrl+C 停止服务器。可通过 `PORT` 环境变量修改端口。

请使用上述本地 HTTP 服务器，不要直接双击 `dist/index.html`：Chrome 对 `file://` 页面中的 ES 模块有限制。

## 安装依赖与开发

如果克隆了整个 `AI` 仓库，先执行 `cd bellworks` 进入项目子目录。如果使用独立压缩包，直接进入解压后的 `Bellworks` 目录即可。下列命令均在项目目录中运行。

开发环境需要 **Node.js 22.12+**（也支持 24）和 npm。首次安装依赖需要访问 npm 仓库；构建后的成品运行不需要联网。

```sh
npm ci
npm run dev
```

在浏览器中打开 http://localhost:5173。所有依赖均在 `package.json` 和 `package-lock.json` 中锁定版本。

```sh
npm run build       # 生成完整的 dist 生产构建
npm run preview     # 在 4173 端口预览生产构建
npm run offline     # 仅使用 Node.js 内置模块提供 dist 静态服务
```

物理引擎文件较大是正常现象：`rapier3d-compat` 将 WASM 内嵌在本地 JavaScript 文件中，运行时不会另行下载 WASM。

## 操作方式

| 控件或操作 | 功能 |
| --- | --- |
| Release the ball | 释放初始钢球，由重力启动链式反应 |
| Pause / Resume | 暂停或继续整个物理世界 |
| Reset | 重建全部刚体与关节，清空碰撞状态、阶段标记及计时 |
| Normal / Slow | 正常速度或四分之一速度；物理步长始终为 1/120 秒 |
| 鼠标左键拖动 | 环绕旋转视角 |
| 鼠标右键拖动 | 平移视角 |
| 鼠标滚轮 | 缩放 |
| 十字准星／俯视／目标按钮 | 恢复默认视角／俯视／跟随钢球 |
| 音符按钮 | 开启或关闭本地合成钟声 |
| 空格键 | 释放钢球，之后切换暂停与继续；按钮获得键盘焦点时采用按钮自身的键盘行为 |

阶段追踪读取真实运动和碰撞。只有发生**击槌与钟体的物理碰撞**，才会显示完成提示并播放钟声。完成后物理世界继续运行，让钟和其他机构自然稳定；完成计时记录首次撞钟的时刻。重置会保留当前视角和所选速度。

## 物理干预模式

新增的 **Physics Intervention** 面板提供两个独立开关，默认关闭，保留原有九阶段机器：

- **Remove Domino（移除骨牌）**：移除第 **08** 块骨牌，即横跨轨道的末块闸片，同时移除它的刚体、碰撞体和可见模型。
- **Add Obstacle（添加障碍）**：在第一段斜坡、骨牌前方加入红色固定挡板。挡板横跨两侧护栏，显示尺寸与 Rapier 方盒碰撞体一致。

释放钢球前，点击开关会立即重建尚未启动的物理世界并应用设置。实验已经启动后（包括暂停状态），切换开关会暂存设置，面板显示“Changes queued”，点击 **Reset** 后才应用。重置时两个选项会一起生效；关闭两项并重置即可恢复原配置。原有开始、暂停、速度和相机控件继续可用。

阶段追踪始终依据真实运动和碰撞。球被挡住时，模拟时间和其余物体仍正常运行，没有脚本判定失败或强行停止。实测红色挡板会拦住钢球；移除末块骨牌后，链条**仍能继续并更早撞钟**，因为原本横跨轨道的闸片不再阻挡通行。

改动前版本保存在 Git 标签 [`bellworks-before-intervention-20261015`](https://github.com/gordonlu731/AI/tree/bellworks-before-intervention-20261015)，提交为 `0f8d6c0`。快照信息见 `snapshots/before-intervention.json`，详细干预验证记录见 [INTERVENTION_TEST_RESULTS.md（英文）](INTERVENTION_TEST_RESULTS.md)。

## 九个机械阶段

| 阶段 | 机构 | 物理连接方式 |
| --- | --- | --- |
| 1 | 重力斜坡 | 释放钢球，使其沿高处带护栏的斜坡滚动 |
| 2 | 八块骨牌 | 钢球撞倒骨牌，碰撞沿骨牌列传递；横跨轨道的末块骨牌必须倒下才能通行 |
| 3 | 摆动闸门 | 同一颗钢球撞开悬挂摆门 |
| 4 | 下降回旋轨道 | 经过 180° 下降弯道，在三维空间中转向，进入较低的反向轨道 |
| 5 | 叶轮 | 钢球通过碰撞带动四叶轮绕转轴旋转 |
| 6 | 跷板桥 | 钢球穿过带配重和关节限位的杠杆桥，跨越真实轨道缺口 |
| 7 | 翻斗 | 钢球进入带挡边的托盘，改变平衡，使托盘翻转并将球送入更低的接球轨道 |
| 8 | 悬挂击槌 | 钢球将动量传给可以自由摆动的击槌 |
| 9 | 悬挂钟 | 击槌摆向钟体，撞击其凸包刚体碰撞体，使钟摆动并发声 |

最终撞钟前有八个阶段。机构由重力、碰撞响应和被动旋转关节驱动，**不使用阶段电机、脚本冲量、物体瞬移、预设运动动画或定时释放**。阶段检测不会改变物理世界。启动操作仅将初始钢球从固定刚体切换为动态刚体。

装饰支架与行进表面分离；活动机构和行进表面均具有物理碰撞体。

## 测试与验证

```sh
npm run test:physics
npm run test:interventions
npm run build
# 在另一个终端执行 npm run offline 后，再运行：
npm run test:browser
npm run test:interventions:browser
```

浏览器测试使用 Playwright 和 Chrome／Chromium。Linux 默认使用 `/usr/bin/chromium`；其他平台默认使用 Playwright 安装的 Chromium。可以通过 `CHROME_PATH` 指定已安装的浏览器，也可以执行 `npx playwright install chromium` 安装测试浏览器。

Windows PowerShell 示例：

```powershell
$env:CHROME_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run test:browser
```

`TEST_URL` 可以指定其他本地端口。浏览器测试针对生产构建，拦截所有非本机回环地址的网络请求，并将截图及机器可读结果保存到 `artifacts/`。

已验证三轮独立物理整链运行、一次浏览器实时整链运行和两次重置后的浏览器物理步进运行，均完成全部九个阶段，首次撞钟发生在约 **14.825 模拟秒**。未释放钢球和锁住末块骨牌的反向检查也通过。

完整测试记录及限制见 [TEST_RESULTS.md（英文）](TEST_RESULTS.md)。测试在 Linux 云环境的 Chromium 中进行，**尚未进行原生 Windows Chrome 测试**。

## 项目结构

- `src/machine.js`：独立于渲染器的 Rapier 物理世界、几何体、关节和碰撞观测。
- `src/scene.js`：Three.js 场景、程序化模型、光照、阴影、相机与静态几何合并。
- `src/main.js`：固定步长循环、交互控件、阶段显示与本地合成音频。
- `src/style.css`：响应式界面，仅使用系统字体。
- `tools/serve.mjs`：不依赖第三方 npm 包的离线静态服务器。
- `tests/`：物理和浏览器回归检查。
- `dist/`：可离线运行的生产构建，已包含在压缩包中；仓库源码目录可通过 `npm run build` 生成。

使用 `?test=1` 可以启用仅用于测试的固定步长加速接口。它执行相同的物理求解，不会直接设置阶段、重新定位物体或注入冲量。普通页面只通过 `window.__bellworks` 提供只读诊断快照。

## 用这台机器测试 AI 的物理预测

另有一套[物理预测盲测材料和操作指南](evaluation/README.zh-CN.md)。只把 **[AI 输入包](evaluation/Bellworks-AI-Input.zip)** 中的初始截图、参数和空白预测表交给新的 AI 对话；实测答案与评分工具单独保留。先保存预测，再揭晓结果。它是小型场景测试，尚未收集独立 AI 的正式预测成绩。

## 运行条件与限制

- 需要支持 WebGL2、显卡驱动正常的 Chrome，建议开启硬件加速。软件渲染可能比现实时间慢，14.825 秒指模拟时间。
- 帧停顿后，固定步长循环会限制补算量；从后台标签页返回时不会突然快进整条链。
- 钟体使用与外形匹配的实心凸包碰撞体，并非中空声学模型；钟声为本地合成音效，不是声学仿真。
- 回旋阶段是下降半圈弯道，不是多圈漏斗。
- 成品运行不依赖外部资源或服务。新电脑从源码重新构建时，需要先联网安装 npm 依赖，或提前准备完整 npm 缓存；Node.js 和 Chrome 也需预先安装。

## 第二轮 AI 物理预测实验

独立页面为 `http://127.0.0.1:4173/round2.html`，原首页保持不变。新页面允许选择 REF 和四个独立初始配置，保留原有交互与九阶段观测规则。

测试 AI 时，只给它 [第二轮 A 包](evaluation/round2/Bellworks-Round2-AI-Input.zip)；[第二轮 B 包](evaluation/round2/Bellworks-Round2-Operator-Kit.zip) 包含实测答案，留给主持人评分。上传方法、预测锁定与评分命令见 [第二轮中文指南](evaluation/round2/README.zh-CN.md)。不要把整个项目或评分包上传给被测 AI。

第二轮改动前的恢复点为 Git 标签 `bellworks-before-round2-20261016`，信息见 `snapshots/before-round2.json`。

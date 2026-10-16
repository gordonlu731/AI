# AI

**English** | [简体中文](README.zh-CN.md)

A collection of independent projects. Each project keeps its source, dependencies, build configuration, documentation and release package in its own directory.

## Projects

### [The Bellworks](bellworks/)

A browser-based 3D Rube Goldberg machine with nine physical stages, built with Three.js and Rapier.

- [Project documentation](bellworks/README.md) · [中文说明](bellworks/README.zh-CN.md)
- [Complete offline package](bellworks/Bellworks.zip) — open this file on GitHub and select **Download raw file**.
- [Test results](bellworks/TEST_RESULTS.md)
- [AI physics prediction kit](bellworks/evaluation/README.md)

For development, start in the project directory:

```sh
cd bellworks
npm ci
npm run dev
```

For offline execution, extract `bellworks/Bellworks.zip`, install Node.js 22 in advance, and run `start-offline.bat` in the extracted folder.

[第二轮 AI 物理预测测试 / Round 2](bellworks/evaluation/round2/README.zh-CN.md)：初始输入与实测评分包分开提供。

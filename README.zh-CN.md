# AI

[English](README.md) | **简体中文**

这个仓库用于存放多个独立项目。每个项目的源码、依赖声明、构建配置、使用说明和离线包都保存在自己的子文件夹中。

## 项目列表

### [The Bellworks：鲁布·戈德堡机械装置](bellworks/)

基于 Three.js 和 Rapier 的浏览器三维机械装置，包含九个通过真实物理交互连接的阶段，最终由击槌撞响钟。

- [中文项目说明](bellworks/README.zh-CN.md)
- [英文项目说明](bellworks/README.md)
- [完整离线包](bellworks/Bellworks.zip)：打开 GitHub 文件页面后，点击 **Download raw file** 下载。
- [测试报告（英文）](bellworks/TEST_RESULTS.md)

开发时，从仓库根目录进入项目子文件夹：

```sh
cd bellworks
npm ci
npm run dev
```

开发环境需要 Node.js 22.12+ 和 npm，首次安装依赖需要联网。

离线使用时，提前安装 Node.js 22，下载并解压 `bellworks/Bellworks.zip`，双击解压目录中的 `start-offline.bat`，再在 Chrome 中打开 http://127.0.0.1:4173。运行预构建的离线包无需联网，也无需执行 `npm install`。

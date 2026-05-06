# Audio2Text - 实时音频转字幕

一个全栈实时音频转文字系统，支持捕获浏览器标签页音频并实时显示字幕。

## 系统架构

```
┌─────────────────┐     WebSocket      ┌─────────────────┐     DashScope API     ┌─────────────────┐
│  Edge 浏览器扩展  │ ──────────────────▶ │  Python 服务端   │ ◀──────────────────▶ │   阿里云语音识别   │
│  (音频捕获)      │     PCM 音频流      │  (中转处理)      │      实时识别         │   (Paraformer)   │
└─────────────────┘                    └────────┬────────┘                       └─────────────────┘
                                                │
                                                │ 事件总线
                                                ▼
                                       ┌─────────────────┐
                                       │  PyQt6 字幕窗口  │
                                       │  (悬浮显示)      │
                                       └─────────────────┘
```

## 功能特性

- **浏览器音频捕获**：使用 Edge 扩展的 tabCapture API 捕获任意标签页音频
- **实时语音识别**：对接阿里云 DashScope Paraformer 实时语音识别
- **悬浮字幕窗口**：透明背景、置顶显示、可拖拽、支持鼠标穿透
- **多标签页支持**：可同时捕获多个标签页的音频

## 快速开始

### 1. 安装 Python 依赖

```bash
cd server
pip install -r requirements.txt
```

### 2. 配置阿里云 API Key

```bash
cd server
cp .env.example .env
# 编辑 .env 文件，填入你的 DASHSCOPE_API_KEY
```

获取 API Key: https://dashscope.console.aliyun.com/apiKey

### 3. 安装 Edge 扩展

1. 打开 Edge 浏览器，访问 `edge://extensions/`
2. 开启"开发人员模式"
3. 点击"加载解压缩的扩展"
4. 选择 `edge-extension` 文件夹
5. 注意：需要先将 `icons/icon.svg` 转换为 PNG 格式

### 4. 启动服务

```bash
cd server
python main.py
```

### 5. 使用

1. 在 Edge 中打开任意有音频的网页（如 YouTube、Bilibili）
2. 点击扩展图标
3. 点击"开始捕获音频"
4. 字幕窗口将实时显示识别结果

## 项目结构

```
audio2text/
├── edge-extension/          # Edge 浏览器扩展
│   ├── manifest.json        # 扩展配置
│   ├── background.js        # Service Worker
│   ├── offscreen.html/js    # 音频处理
│   ├── popup.html/js        # 弹出窗口
│   └── icons/               # 扩展图标
│
├── server/                  # Python 服务端
│   ├── main.py              # 主入口
│   ├── websocket_server.py  # WebSocket 服务器
│   ├── speech_recognizer.py # 语音识别封装
│   ├── subtitle_window.py   # PyQt6 字幕窗口
│   ├── event_bus.py         # 事件总线
│   └── requirements.txt     # Python 依赖
│
├── start.bat                # Windows 快速启动脚本
└── README.md                # 本文件
```

## 技术栈

- **前端扩展**：JavaScript, Manifest V3, Web Audio API, WebSocket
- **后端服务**：Python 3.10+, asyncio, websockets
- **语音识别**：阿里云 DashScope (Paraformer-Realtime)
- **桌面 UI**：PyQt6

## 常见问题

### Q: 捕获音频后听不到声音？
A: 扩展代码中已将音频流同时连接到 `audioContext.destination`，确保用户能听到声音。如果仍有问题，请检查系统音量设置。

### Q: 字幕延迟很高？
A: 正常延迟在 200-500ms 左右。如果延迟过高，请检查网络连接和阿里云 API 响应时间。

### Q: 如何调整字幕窗口位置？
A: 直接拖拽字幕窗口即可。右键系统托盘图标可以锁定位置（启用鼠标穿透）。

## License

MIT

---

# Git 与代码版本管理——实践报告

> 24级 2026年春季学期 读书实践周任务
>
> 人工智能专业

## 一、学习资料来源与相关链接

| 资源名称 | 链接 | 说明 |
|---------|------|------|
| Git 官方文档 | https://git-scm.com/doc | Git 官方参考手册，涵盖所有命令与概念 |
| Pro Git（中文版） | https://git-scm.com/book/zh/v2 | 权威的 Git 学习书籍，从入门到精通 |
| 廖雪峰 Git 教程 | https://www.liaoxuefeng.com/wiki/896043488029600 | 通俗易懂的中文 Git 教程 |
| GitHub Docs | https://docs.github.com/zh | GitHub 官方中文文档 |
| Oh Shit, Git!?! | https://ohshitgit.com/zh | 常见 Git 事故的急救方案 |
| Visualizing Git | https://git-school.github.io/visualizing-git/ | 可视化 Git 操作，直观理解分支与提交 |
| 阿里云 DashScope | https://dashscope.console.aliyun.com/apiKey | 项目中使用的语音识别 API |

## 二、实践流程

### 2.1 Git 环境安装与配置

**安装 Git**

在 Windows 系统下载 [Git for Windows](https://git-scm.com/download/win) 安装包，按默认选项完成安装。Linux（Ubuntu/Debian）下执行：

```bash
sudo apt update && sudo apt install git -y
```

验证安装：

```bash
git --version
# 输出: git version 2.43.0
```

**配置用户信息**

```bash
git config --global user.name "SolarCrown57"
git config --global user.email "2864793565@qq.com"
```

全局配置保存在 `~/.gitconfig` 中，所有仓库默认使用此身份。仓库级覆盖可在项目目录下执行 `git config user.name`（不加 `--global`）。

**配置换行符处理**

Windows 和 Linux 换行符不同（CRLF vs LF），需统一配置避免乱码：

```bash
# Windows
git config --global core.autocrlf true
# Linux/Mac
git config --global core.autocrlf input
```

### 2.2 创建本地仓库

```bash
mkdir audio2text && cd audio2text
git init
```

`git init` 在当前目录创建 `.git` 隐藏目录，包含仓库所有元数据和版本历史。

### 2.3 关联远程仓库

1. 在 GitHub 创建公开仓库 `SolarCrown57/audio2text`
2. 将本地仓库与远程关联：

```bash
git remote add origin https://github.com/SolarCrown57/audio2text.git
git branch -M master
git push -u origin master
```

`-u` 参数设置上游跟踪，后续 `git push` 无需指定远端和分支。

### 2.4 日常开发流程

基本工作循环如下：

```bash
git status                 # 查看文件变更状态
git add <file>             # 将变更添加到暂存区
git commit -m "提交说明"    # 提交暂存区的变更
git push origin master     # 推送到远程仓库
```

工作区 → 暂存区（`git add`） → 本地仓库（`git commit`） → 远程仓库（`git push`）

### 2.5 .gitignore 配置

创建 `.gitignore` 文件排除不应版本跟踪的文件：

```
.env          # 环境变量（含 API 密钥）
__pycache__/  # Python 缓存
venv/         # 虚拟环境
.vscode/      # IDE 配置
*.log         # 日志文件
```

## 三、提交记录说明

本项目共计 4 次提交，均在 `master` 分支上完成。

### 提交 1：Initial commit

**SHA**: `4a63915`

**内容**：项目初始提交，包含完整的 Audio2Text 系统代码。

**变更文件**：
- `server/` — Python 服务端（WebSocket 服务器、语音识别封装、字幕窗口、事件总线）
- `edge-extension/` — Edge 浏览器扩展（音频捕获、弹窗控制）
- `start.bat` — Windows 启动脚本
- `.gitignore` — 版本忽略规则
- `README.md` — 项目说明文档

### 提交 2：修复 offscreen.js 音频处理 bug

**SHA**: `72669de`

**Bug 描述**：前端音频采样位深转换函数 `floatTo16BitPCM` 中对正负信号使用了不同的量化因子（`0x8000` vs `0x7FFF`），造成极性不对称失真；`AudioContext.close()` 返回 Promise 但未处理，导致未捕获的 rejection。

**修复内容**：
- 统一使用 `Math.round(s * 0x7FFF)` 作为量化公式，消除非对称失真
- 添加 `.catch()` 链式处理 `close()` 的异步错误

### 提交 3：修复服务端健壮性问题

**SHA**: `d322dfe`

**Bug 描述**：
1. WebSocket 连接在未完成 init 握手前断开时，`tab_id` 变量为 `None`，日志输出 `[Tab None]` 不利于问题排查
2. 字幕窗口高度在无活跃标签页时，仍按 1 个标签页计算高度，导致窗口比实际需要更大

**修复内容**：
- `websocket_server.py`：使用 `tab_id or 'unknown'` 兜底处理空值
- `subtitle_window.py`：`adjust_height` 方法改为使用实际 tab 数量（可为 0）

### 提交 4：修复 speech_recognizer SDK 类型兼容性

**SHA**: `4749470`

**Bug 描述**：DashScope SDK 的 `RecognitionResult.get_sentence()` 返回 `Sentence` 对象（属性访问如 `.text`、`.end_time`），而代码中使用了 dict 风格的 `.get('text', '')` 调用，运行时抛出 `AttributeError`。

**修复内容**：使用 `hasattr` 判断返回值的访问方式，兼容 dict 和对象两种返回类型，确保在不同 SDK 版本下都能正常工作。

### 提交 5：更新 README 实践报告

**SHA**: 当前提交

**内容**：编写完整的 Git 实践报告，包含学习资料、实践流程、提交说明、遇到的问题及心得。

## 四、遇到的问题及解决方法

### 问题 1：Git 提交时中文乱码

**现象**：在 Windows 系统使用 `git log` 查看提交记录时，中文提交信息显示为乱码（形如 `<E6><8F><90>`）。

**排查过程**：使用 `git config --list` 查看配置，发现 `core.quotepath` 为 `false` 但 `i18n.commitEncoding` 未设置。

**解决方法**：

```bash
git config --global i18n.commitEncoding utf-8
git config --global i18n.logOutputEncoding utf-8
# Windows 还需设置终端编码
git config --global core.quotepath false
```

此外，在 Windows 命令行中使用 `chcp 65001` 切换到 UTF-8 编码页。

**教训**：跨平台开发时应统一字符编码配置，避免团队协作时出现乱码。

### 问题 2：提交后才发现遗漏文件

**现象**：执行 `git commit` 后，发现有一个修改的文件忘了 `git add`，导致提交不完整。

**解决方法**：

```bash
# 方法1：补充遗漏文件到上次提交
git add <遗漏文件>
git commit --amend --no-edit

# 方法2：如果已 push 且未有人拉取，可强制推送
git push --force-with-lease
```

**重要提示**：`--amend` 会修改提交历史，仅适用于尚未推送到远程共享分支的提交。如果其他协作者已经拉取了该提交，应创建新提交而非改写历史。

### 问题 3：不小心提交了含敏感信息的文件

**现象**：将包含 API Key 的 `.env` 文件误加入版本控制。

**排查过程**：检查 `.gitignore` 文件，发现文件存在但配置不完全——只忽略了 `.env`，未加入 `.env` 相关的变体文件。

**解决方法**：

```bash
# 1. 从 Git 跟踪中移除（保留本地文件）
git rm --cached .env

# 2. 确保 .gitignore 已添加该文件
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore

# 3. 立即更换已泄露的 API Key
# 在阿里云控制台重新生成 Key

# 4. 提交变更
git add .gitignore
git commit -m "chore: 从跟踪中移除 .env 文件，防止密钥泄露"
```

此问题说明了 `.gitignore` 必须在首次提交前配置好，一旦敏感信息进入版本历史，即使删除文件，历史记录中仍留有备份。

## 五、Git 学习心得

### 理解"暂存区"是关键

初次接触 Git 时，最大的困惑来自"为什么需要 `git add` 再 `git commit`？" 理解了暂存区的设计理念后豁然开朗：暂存区就像一个"草稿箱"，它允许从工作区的多个修改中**选择性提交**，而非全量提交。这种精细控制在实际开发中非常有用——可以先提交 bug 修复，再单独提交格式调整，保持每次提交的**原子性和可读性**。

### 提交信息是写给未来自己的信

每次 `git commit -m "fix bug"` 是一颗定时炸弹。在本次实践中刻意练习了规范的提交信息格式：

```
<type>: <subject>
```

- `fix:` 表示修复 bug
- `feat:` 表示新功能
- `chore:` 表示杂项任务

好的提交信息让三个月后的自己也能秒懂当时的意图，也让团队成员能通过 `git log --oneline` 快速了解项目演化脉络。

### 版本控制是一种工程习惯

Git 的价值不仅在于"保存代码"，更在于它迫使开发者建立一种纪律：**每次修改都有记录，每次提交都有理由，任何版本都可回溯**。在没有版本控制的年代，代码备份靠复制文件夹（如 `project_v1/`、`project_v2_final/`、`project_v2_final_really/`），一旦出问题难以定位。Git 让"大胆尝试、安全回退"成为可能，这是工程化开发的基础。

### 未来的进阶方向

本次实践完成了 Git 的基本操作，后续计划深入学习：

- **分支管理**：`git branch`、`git merge`、`git rebase` 实现并行开发与功能隔离
- **协作流程**：Fork + Pull Request 的 GitHub 协作模式
- **交互式 rebase**：用 `git rebase -i` 整理提交历史，保持主线整洁
- **Git Hooks**：在 commit/push 时自动运行 lint、测试等检查
- **CI/CD 集成**：GitHub Actions 实现提交即构建、测试、部署

---

> 作者：SolarCrown57 &lt;2864793565@qq.com&gt;
>
> 仓库地址：https://github.com/SolarCrown57/audio2text

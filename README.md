# HX-AIBOT

## 中文说明

HX-AIBOT 是一个面向 Windows 的桌面工具，用来抓取目标窗口、调用兼容 `chat/completions` 的 AI 接口分析题目，并根据识别结果执行自动答题辅助流程。

### 主要功能

- 通过黄色透明十字准星选择目标窗口
- 截取目标窗口画面并发送到你配置的 AI 接口
- 使用 OCR 识别选项区域，并优先点击匹配到的选项文字本身
- 支持单选、多选、下一题按钮、提交按钮的辅助定位
- 提供 `中文 / English` 界面切换
- 提供明亮 / 黑暗主题切换，按钮分别使用太阳 `☀` 与月亮 `☾` 图标
- 提供 Qt 桌面界面与打包脚本

### 运行环境

- Windows 10 / 11
- Python 3.9 及以上

### 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 启动方式

推荐启动 Qt 版界面：

```powershell
python qt_app.py
```

如果你要使用原始 Tk 版界面，也可以运行：

```powershell
python app.py
```

### 打包

```powershell
powershell -ExecutionPolicy Bypass -File .\build_qt.ps1
```

打包完成后，输出目录通常位于：

- `dist/HX-AIBOT`
- `dist/HX-AIBOT_portable.zip`

### 配置说明

首次使用时请在“设置”中填写：

- API 地址
- API Key
- 模型 ID / Endpoint ID
- 超时秒数
- 分析提示词

程序会将这些配置保存在本地 `settings.json` 中。

### 隐私说明

HX-AIBOT 默认不会把数据上传到开发者自建服务器，但当你主动执行截图分析、自动答题或相关操作时，截图内容、提示词和请求参数会发送到你在设置中填写的第三方 AI 接口。

提交微软商店前，请准备可公开访问的隐私政策页面，或将本仓库中的 [PRIVACY_POLICY.md](./PRIVACY_POLICY.md) 内容发布到你自己的站点或商店隐私政策入口中。如果你需要直接粘贴到商店后台，也可以使用纯文本版 [PRIVACY_POLICY_STORE_PLAIN.txt](./PRIVACY_POLICY_STORE_PLAIN.txt)。

### 许可

本项目采用 [GNU General Public License v3.0](./LICENSE) 许可发布。

## English

HX-AIBOT is a Windows desktop utility for selecting a target window, capturing screenshots, sending them to a `chat/completions` compatible AI endpoint, and assisting with automated quiz workflows based on the returned answers.

### Features

- Select a target window with a lightweight translucent yellow crosshair
- Capture the selected window and send it to your configured AI endpoint
- Use OCR to detect answer regions and click the matched answer text directly
- Support helper positioning for options, next-question button, and submit button
- Switch the interface between `Chinese / English`
- Switch between light and dark themes with sun `☀` and moon `☾` buttons
- Includes a Qt desktop UI and a packaging script

### Requirements

- Windows 10 / 11
- Python 3.9+

### Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Launch

Recommended Qt UI:

```powershell
python qt_app.py
```

Legacy Tk UI:

```powershell
python app.py
```

### Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build_qt.ps1
```

Build outputs are typically generated at:

- `dist/HX-AIBOT`
- `dist/HX-AIBOT_portable.zip`

### Configuration

Open `Settings` and fill in:

- API URL
- API Key
- Model ID / Endpoint ID
- Timeout seconds
- Analysis prompt

These values are stored locally in `settings.json`.

### Privacy Note

HX-AIBOT does not send data to a developer-operated backend by default. However, when you actively run screenshot analysis, auto-solving, or related automation, screenshots, prompts, and request parameters are sent to the third-party AI endpoint that you configure in Settings.

Before publishing to Microsoft Store, host a public privacy policy page or publish the content from [PRIVACY_POLICY.md](./PRIVACY_POLICY.md) through your own site or Store privacy policy entry. If you need a copy-and-paste version for the Store backend, use [PRIVACY_POLICY_STORE_PLAIN.txt](./PRIVACY_POLICY_STORE_PLAIN.txt).

### License

This project is released under the [GNU General Public License v3.0](./LICENSE).

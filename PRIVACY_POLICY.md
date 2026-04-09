# HX-AIBOT Privacy Policy / HX-AIBOT 隐私政策

Effective Date / 生效日期: 2026-04-10

## 中文版

### 1. 适用范围

本隐私政策适用于 HX-AIBOT Windows 桌面应用，以及与其相关的本地配置、截图分析和自动答题辅助功能。

### 2. 我们处理的数据

HX-AIBOT 默认在你的设备本地运行。根据你的使用方式，程序可能处理以下数据：

- 本地配置数据：API 地址、API Key、模型 ID、超时秒数、提示词、按钮定位坐标、界面语言、主题设置
- 本地运行数据：日志文本、窗口标题、窗口位置、按钮定位信息
- 截图数据：当你主动执行截图、单次分析或自动答题时，程序会读取目标窗口图像
- 本地文件数据：当你使用“保存截图”功能时，截图会保存在本机 `captures/` 目录

### 3. 数据如何被发送

当你主动触发以下功能时：

- 单次答题
- 自动答题
- 其他依赖截图分析的功能

程序会将当前截图、分析提示词以及必要的请求参数发送到你在“设置”中填写的第三方 AI 接口。

HX-AIBOT 默认不会把这些数据发送到开发者自建服务器，但你配置的第三方 AI 服务提供方可能会接收并处理这些数据。你应当同时阅读并遵守该第三方服务的隐私政策与服务条款。

### 4. 数据用途

处理上述数据的目的包括：

- 识别题目、选项与答案
- 生成题目解析结果
- 辅助自动点击选项、下一题和提交按钮
- 保存你的本地设置，避免每次重复配置
- 改善你在本地设备上的操作体验

### 5. 数据存储与保留

- `settings.json` 中的配置会保存在你的本地设备，直到你手动修改或删除
- 日志默认显示在应用界面内，不会自动上传到开发者服务器
- 只有在你主动点击“保存截图”时，截图才会写入本地文件
- 发送到第三方 AI 接口的数据，其保存时间和处理方式由该第三方服务提供方决定

### 6. 数据共享

除以下情况外，HX-AIBOT 默认不会向第三方共享你的数据：

- 你主动配置并使用第三方 AI 接口
- 法律法规要求披露
- 为了响应司法、监管或安全合规要求

### 7. 你的控制权

你可以通过以下方式控制数据处理：

- 不填写 API Key 或不启用截图分析功能
- 删除本地 `settings.json`
- 删除本地 `captures/` 文件
- 改用你信任的 AI 服务提供方
- 停止使用本软件

### 8. 儿童隐私

HX-AIBOT 不是专门面向儿童设计的应用。请不要使用本应用处理你无权处理的敏感信息、未成年人信息或受保护数据。

### 9. 微软商店说明

如果你通过微软商店分发 HX-AIBOT，请确保商店页面提供可访问的隐私政策链接或对应的隐私政策内容。由于本应用允许用户输入 API 凭据并将截图发送到用户指定的第三方 AI 服务，因此发布者应确保商店披露内容与你实际分发版本一致。

### 10. 联系方式

发布到微软商店前，请将这里替换为你的真实支持邮箱或隐私联系渠道。

- 联系邮箱：`[请在发布前替换]`

### 11. 政策更新

如果本隐私政策发生变化，发布者应更新此文档中的日期与内容，并在商店或应用发布页同步更新。

## English

### 1. Scope

This Privacy Policy applies to the HX-AIBOT Windows desktop application and its related local configuration, screenshot analysis, and quiz automation assistance features.

### 2. Data We Process

HX-AIBOT runs locally on your device by default. Depending on how you use the app, it may process:

- Local configuration data: API URL, API Key, model ID, timeout, prompts, button coordinates, interface language, and theme preference
- Local runtime data: log text, window titles, window bounds, and button locator data
- Screenshot data: the target window image when you actively run capture, analysis, or auto-solving
- Local file data: screenshots saved to the local `captures/` folder when you use the Save Screenshot feature

### 3. How Data Is Sent

When you actively trigger:

- Analyze Once
- Auto-solving
- Other screenshot-based analysis features

the app sends the current screenshot, analysis prompt, and required request parameters to the third-party AI endpoint that you configure in Settings.

HX-AIBOT does not send this data to a developer-operated backend by default. However, the third-party AI provider you configure may receive and process that data. You should also review that provider's privacy policy and terms of service.

### 4. Why Data Is Used

The data above is processed in order to:

- Detect questions, options, and answers
- Generate answer reasoning
- Assist with automatically clicking answer options, the next button, and the submit button
- Save your local preferences so you do not need to reconfigure the app each time
- Improve your local desktop workflow

### 5. Storage and Retention

- Configuration stored in `settings.json` remains on your local device until you edit or delete it
- Logs are shown inside the app and are not automatically uploaded to a developer server
- Screenshots are only written to disk when you explicitly choose Save Screenshot
- Data sent to a third-party AI endpoint is retained according to that provider's own policies

### 6. Data Sharing

HX-AIBOT does not share your data with third parties by default, except when:

- You intentionally configure and use a third-party AI endpoint
- Disclosure is required by law
- Disclosure is necessary for judicial, regulatory, or security compliance

### 7. Your Choices and Controls

You can control data processing by:

- Not entering an API Key or not using screenshot analysis features
- Deleting the local `settings.json`
- Deleting local files in `captures/`
- Choosing an AI provider you trust
- Stopping use of the application

### 8. Children's Privacy

HX-AIBOT is not designed specifically for children. Do not use the app to process sensitive information, minors' data, or protected data that you are not authorized to handle.

### 9. Microsoft Store Notice

If you distribute HX-AIBOT through Microsoft Store, make sure the Store listing includes an accessible privacy policy link or equivalent privacy policy content. Because the app allows users to enter API credentials and send screenshots to a user-selected third-party AI service, the publisher should ensure the Store disclosure matches the actual distributed version.

### 10. Contact

Before Microsoft Store submission, replace this section with your real support email or privacy contact channel.

- Contact email: `[replace before submission]`

### 11. Policy Updates

If this Privacy Policy changes, the publisher should update the date and contents of this document and keep the Store or product page in sync.

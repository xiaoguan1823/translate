# 翻译工具

一个常驻系统托盘的 Windows 划词翻译小工具：复制文本 → 按快捷键 → 屏幕中央弹出译文，点击译文即可复制。

## 功能

- **全局快捷键唤出**，默认 `Ctrl+T`，可在设置中任意修改
- **剪贴板翻译**：不会主动读屏，只翻译你自己复制的文本
- **智能互译**：自动识别中/英/日/韩等语言，中文↔英文自动切换方向，也可指定固定目标语言
- **多翻译平台**：Google（免配置）、DeepL、百度、有道
- **弹窗自动关闭**：鼠标离开弹窗约 4 秒后自动隐藏，按 `Esc` 立即关闭
- **深色模式**、**系统托盘**、**自动读取系统代理**

## 环境要求

- Windows 10 / 11
- Python 3.8+

> 程序依赖 `ctypes.windll`、`winreg` 等 Windows 接口，目前仅支持 Windows。

## 快速开始

**方式一：双击 `启动翻译.bat`**

会自动检测 Python、安装依赖并启动，首次运行需要联网安装依赖。

**方式二：手动运行**

```bash
pip install -r requirements.txt
python main.py
```

启动后会显示主窗口，8 秒后自动隐藏到系统托盘。之后：

1. 复制任意文本（`Ctrl+C`）
2. 按快捷键（默认 `Ctrl+T`）
3. 屏幕中央弹出原文与译文
4. 点击译文复制，按 `Esc` 或把鼠标移开即可关闭

右键托盘图标可显示主窗口或退出。

## 翻译平台

在「翻译设置」中选择平台：

| 平台 | 是否需要密钥 | 获取地址 |
| --- | --- | --- |
| Google 翻译 | 不需要 | — |
| DeepL | API Key | https://www.deepl.com/pro-api |
| 百度翻译 | App ID + App Key | https://fanyi-api.baidu.com/ |
| 有道翻译 | App ID + App Key | https://ai.youdao.com/ |

百度/有道的免费额度对个人使用通常够用。

## 配置文件

配置保存在 `translator_config.json`，首次启动时自动生成：

- 源码运行：保存在 `main.py` 同目录
- exe 运行：保存在 `%APPDATA%\翻译工具\`

**这个文件包含你的 API 密钥，已被 `.gitignore` 排除，请不要提交到仓库。** 需要参考格式时看 `translator_config.example.json`。

主要字段：

| 字段 | 说明 |
| --- | --- |
| `provider` | 翻译平台：`google` / `deepl` / `baidu` / `youdao` |
| `target_lang` | 目标语言，智能互译关闭时生效 |
| `smart_mode` | `true` 时自动中↔英，忽略 `target_lang` |
| `hotkey` | 快捷键，如 `{"modifiers": ["ctrl"], "key": "t"}` |
| `dark_mode` | 深色模式 |

代理会自动读取 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量，或使用 Windows 系统代理设置。

## 打包为 exe（可选）

```bash
pip install pyinstaller
pyinstaller -F -w --name 翻译工具 main.py
```

产物在 `dist/` 目录。发布时建议把 exe 上传到 GitHub Releases 的附件，而不是提交进仓库。

## 说明

- 有道翻译通过官方开放 API 直连，使用 MD5 签名验证
- 翻译失败（如网络不通、密钥错误）会在主窗口状态栏提示

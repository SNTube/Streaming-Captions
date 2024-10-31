# Streaming Captions

Streaming Captions 基于 [streaming-sensevoice](https://github.com/pengzhendong/streaming-sensevoice) 项目，实现类似win11的 `LiveCaptions` 的实时字幕，加入多行文本处理后 `复制到剪贴板` 以适配 [Lunatranslator](https://github.com/HIllya51/LunaTranslator) 的剪贴板识别模式

PS: 因为不会用 `python` 实现 `捕获内录音` ，所以需要安装 `Virtual Audio Cable (VAC) Lite版` 作为 `内录音输入设备` 。

## 使用

- 克隆项目

```bash
git clone -b dev/gui-development https://github.com/SNTube/Streaming-Captions.git
```

- 安装依赖

cd 到 项目目录下，执行

```bash
pip install -r requirements.txt
```

- 安装VAC作为内录

1. 用[Virtual Audio Cable (VAC)](https://vac.muzychenko.net/en/)作为内录接口，下载安装包 ( 这东西不好卸载，卸载时请用GeekUninstaller之类的卸载工具 ) 。

2. 把安装后显示的播放设备 `Line 1` 设置为默认设备 ( 即 `设为默认值` ) 。

3. 安装后显示的录制设备 `Line 1` ，选中并点开 `属性` ，在 `侦听` 分页中，勾选 `侦听此设备` ，`通过此设备播放` 选择 `原本的扬声器设备`，`应用` 并 `确定`。

4. 显示的录制设备中，选择 `实际存在的麦克风设备` 作为默认设备 ( 即 `设为默认值` ) 。

- 运行脚本

```bash
python StreamingCaptions.py
```
界面一览无遗，简洁大方，清晰明了，没有需要介绍的部分。

如有 Bug 请提 Issues ，我编程水平靠AI，能不能解决只能是看情况。 

## 使用 Lunatranslator 翻译字幕

 `Lunatranslator` 如何使用不做赘述，仅说明相关部分

-  Lunatranslator 设置

1. 点开 `Lunatranslator` 的 `设置` (齿轮图标) 

2. `文本输入` 分栏中，`选择文本输入源` 开启 `剪贴板` 开关

3. `文本处理` 分栏中，开启并从上到下排序 `去除重复字符AAAABBBBCCCC->ABC` 、`去除重复行AABABCABCD->ABCD` 、`过滤换行符` 。

## 协议声明

本项目基于[streaming-sensevoice](https://github.com/pengzhendong/streaming-sensevoice) 项目，原项目采用了 `Apache License 2.0` 许可。

- 所以本项目声明如下

1. 本项目采用了 `Apache License 2.0` 许可

2. 本项目中，保留的所有原始文件，已保留其中所有的版权声明、专利声明、商标声明及归属声明。

3. 说明修改与新增内容
	* 删去了没有使用的运行文件、演示音频、演示图片
	* 增加一个SC_SNTube.ico图标作为窗口图标
	* StreamingCaptions.py为GUI界面，并在其中包含声明

# Streaming Captions

Streaming Captions 基于 [streaming-sensevoice](https://github.com/pengzhendong/streaming-sensevoice) 项目，实现类似win11的 `LiveCaptions` 的实时字幕，加入 `kernel32.dll` 处理文本以适配 [Lunatranslator](https://github.com/HIllya51/LunaTranslator) 的 `Hook` 模式 。

PS: 因为不会用 `python` 实现 `捕获内录音` ，所以需要安装 `Virtual Audio Cable (VAC) Lite版` 作为 `内录音输入设备` 。

## 使用

#### 克隆项目

```bash
git clone -b dev/gui-development https://github.com/SNTube/Streaming-Captions.git
```

#### 安装依赖

cd 到 `项目目录` 下，执行

```bash
pip install -r requirements.txt
```

#### 安装VAC作为内录

1. 用[Virtual Audio Cable (VAC)](https://vac.muzychenko.net/en/)作为内录接口，下载安装包。
 ( Virtual Audio Cable这东西不好卸载，卸载时到安装目录内，`以管理员权限运行` `delete_service.cmd` ，然后在用GeekUninstaller之类的卸载工具正常卸载 ) 

2. 把安装后显示的播放设备 `Line 1` 设置为默认设备 ( 即 `设为默认值` ) 。

3. 安装后显示的录制设备 `Line 1` ，选中并点开 `属性` ，在 `侦听` 分页中，勾选 `侦听此设备` ，`通过此设备播放` 选择 `原本的扬声器设备`，`应用` 并 `确定`。

4. 显示的录制设备中，选择 `实际存在的麦克风设备` 作为默认设备 ( 即 `设为默认值` ) 。

PS: 如果没有麦克风设备只想用内录模式，请先安装VAC并将安装后显示的录制设备 `Line 1` 设为默认的麦克风设备。

#### 运行脚本

```bash
python StreamingCaptions.py
```

- 界面一览无遗，简洁大方，清晰明了。

- 现在通过 `kernel32.dll` 摸一下文本，可以被 `Lunatranslator` 的 `Hook` 模式搜到了。

- 功能包括界面宽度、字号大小、优先语言、VAC模式(VAC专用模式)、标点恢复、文本居中与靠左、隐藏界面、隐藏按钮、热词增强、快捷键、复制当前显示文本、更改字体。

#### 热词增强

同目录下放一个 `hotwords.txt` ，一行一个词，可以提升对指定词的准确率。 

如有 `Bug` 请提 `Issues` ，我编程水平靠AI，能不能解决只能是看情况。 

## 使用 Lunatranslator 翻译字幕

 `Lunatranslator` 如何使用不做赘述，仅说明相关部分

#### Lunatranslator 设置

1. 点开 `Lunatranslator` 的 `设置` (齿轮图标) 

2. `核心设置` 分栏中，找到 `文本输入` ，开启 `HOOK` 开关。

3. `HOOK设置` 下，`选择游戏` 齿轮 ，`点击此按钮后点击游戏窗口` 后，点击本实时字幕的界面并·`OK` ，`选择文本` 齿轮，等待识别文字后，激活字幕所在行的前方开关。

4. `文本处理` 分栏中，开启并从上到下排序 `过滤历史重复LRU` 、`去除重复字符AAAABBBBCCCC->ABC` 、`去除重复行AABABCABCD->ABCD` 、`过滤换行符`  、`自定义python处理` 。

5. `自定义python处理` 的齿轮点开，输入下方代码，保存

```python
def POSTSOLVE(line):
    # 请在这里编写自定义处理
    lines = line.splitlines()
    ll = lines【-1】
    return ll
```

## 协议声明

本项目基于[streaming-sensevoice](https://github.com/pengzhendong/streaming-sensevoice) 项目，原项目采用了 `Apache License 2.0` 许可。

- 所以本项目声明如下

1. 本项目采用了 `Apache License 2.0` 许可

2. 本项目中，保留的所有原始文件，已保留其中所有的版权声明、专利声明、商标声明及归属声明。

3. 说明修改与新增内容
	* 删去了没有使用的运行文件、演示音频、演示图片
	* 增加一个SC_SNTube.ico图标作为窗口图标
	* StreamingCaptions.py为GUI界面，并在其中包含声明

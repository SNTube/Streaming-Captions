# Copyright (c) 2024, SNTube Studio (qq869865681@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ctypes
import numpy as np
import sys
import os
from multiprocessing import Process

import sounddevice as sd
# import soundfile as sf
from pysilero import VADIterator
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                            QLabel, QHBoxLayout, QComboBox, QSizePolicy, 
                            QLineEdit, QSlider, QMenu, QAction, QShortcut)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QSettings, 
                         QPoint, QSize, QTimer)
from PyQt5.QtGui import (QColor, QFont, QPainter, QMouseEvent, 
                        QIcon, QKeySequence, QMovie, QPixmap)

from SimplePage import FontListWidget, run_loading_window

# 背景图片缩放系数
SCALE_FACTOR = 1
# 背景窗口X轴偏移量
WINDOW_OFFSET_X = 0
# 背景窗口Y轴偏移量
WINDOW_OFFSET_Y = 0
# 背景窗口透明度
BG_WINDOW_OPACITY = 1

# import multiprocessing
# # 冻结模式检查(编译后防止重复运行进程)
# if not hasattr(sys, 'frozen'):
#     sys.frozen = True

# Windows API 工具函数(加载kernel32.dll库HOOK用)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# 调用MultiByteToWideChar函数
def multi_byte_to_wide_char(mb_str, code_page=65001):
    kernel32.MultiByteToWideChar(code_page, 0, mb_str, -1, None, 0)
    return mb_str

class WideCharThread(QThread):
    def __init__(self, text, parent=None):
        super(WideCharThread, self).__init__(parent)
        self.text = text

    def run(self):
        text_with_newline = self.text + "\r\n"  # 添加换行符(Windows换行格式)
        multi_byte_to_wide_char(text_with_newline.encode('utf-8'))

class SpeechRecognitionThread(QThread):
    """语音识别线程，负责实时处理音频输入并进行语音识别"""
    updateTextSignal = pyqtSignal(str)  # 信号：当识别到新文本时发射

    # 加载热词增强
    def load_hotwords(self):
        # 加载热词文件，为了整洁放SimplePage文件夹下
        start_script_path = os.path.abspath(sys.argv[0])
        base_dir = os.path.dirname(start_script_path)
        hotwords_file = os.path.join(base_dir, "SimplePage/hotwords.txt")
        if not os.path.exists(hotwords_file):
            print(f"文件 {hotwords_file} 不存在")
            print("热词增强关闭")
            return None
        with open(hotwords_file, "r", encoding="utf-8") as f:
            hotwords = [line.strip() for line in f if line.strip()]
            if hotwords:
                return hotwords
            else:
                print(f"文件 {hotwords_file} 内容为空")
                print("热词增强关闭")
        return None

    # 调大chunk_size让句子减少连词情况，但会增加识别时间，默认10
    def __init__(self, input_device_idx, language="auto", textnorm=False, 
                 chunk_size=10, padding=8, beam_size=3, speech_pad_ms=300, 
                 threshold=0.3, min_silence_duration_ms=300):
        # 切换设置时显示加载动画就放这里
        # 再载模型
        """初始化语音识别线程
        参数:
            input_device_idx: 输入设备索引
            language: 识别语言(默认自动检测)
            textnorm: 是否启用标点恢复
            chunk_size: 语音块大小
            padding: 填充大小
            beam_size: beam搜索大小
            speech_pad_ms: 语音填充时间(毫秒)
            threshold: VAD阈值
            min_silence_duration_ms: 最小静音持续时间(毫秒)
        """
        from streaming_sensevoice import StreamingSenseVoice

        super().__init__()

        # 从设置中获取标点恢复配置
        settings = QSettings('SNTube', 'SNTrealtimeSubtitles')
        textnorm = settings.value('textnorm', textnorm, type=bool)

        # 加载热词
        hotwords = self.load_hotwords()
        print(f"加载的热词: {hotwords}")

        # 初始化语音识别模型和VAD
        self.model = StreamingSenseVoice(
            language=language, 
            textnorm=textnorm, 
            contexts=hotwords, 
            chunk_size=chunk_size, 
            padding=padding, 
            beam_size=beam_size
        )
        """
        # 原vad参数
        self.vad_iterator = VADIterator(speech_pad_ms=300)
        """
        self.vad_iterator = VADIterator(
            speech_pad_ms=speech_pad_ms,
            threshold=threshold,
            min_silence_duration_ms=min_silence_duration_ms
        )
        self.input_device_idx = input_device_idx
        self.running = True  # 线程运行标志

    def run(self):
        """线程主执行方法，处理音频输入流"""
        devices = sd.query_devices()
        if len(devices) == 0:
            print("没有找到输入设备，请检查设备是否正常连接")
            return
        """
        # 如果不确定自己的设备列表
        print(devices)
        """
        print(f'所用设备: {devices[self.input_device_idx]["name"]}\n===============================================')

        # 预计算常量
        samples_per_read = int(0.1 * 16000)  # 每次读取的样本数(0.1秒的音频)
        sample_scale = 32768  # 音频样本缩放因子

        # 预分配内存
        audio_buffer = np.zeros(samples_per_read, dtype=np.float32)

        with sd.InputStream(
            channels=1, 
            dtype="float32", 
            samplerate=16000, 
            device=self.input_device_idx,
            blocksize=samples_per_read
        ) as s:
            while self.running:
                try:
                    # 读取音频样本
                    samples, _ = s.read(samples_per_read)
                    if samples.size == 0:
                        continue

                    # 使用预分配内存处理音频
                    np.copyto(audio_buffer, samples[:, 0])

                    # 使用VAD处理音频
                    for speech_dict, speech_samples in self.vad_iterator(audio_buffer):
                        if "start" in speech_dict:  # 检测到语音开始
                            self.model.reset()

                        is_last = "end" in speech_dict  # 是否语音结束

                        # 流式推理(避免重复内存分配)
                        scaled_samples = speech_samples * sample_scale
                        for res in self.model.streaming_inference(scaled_samples, is_last):
                            if res["text"]:  # 只有有文本时才发射信号
                                self.updateTextSignal.emit(res["text"])
                except Exception as e:
                    print(f"音频处理异常: {str(e)}")
                    continue

    def terminate(self):
        """终止线程"""
        self.running = False  # 设置停止标志
        super().terminate()  # 调用父类终止方法

def find_device_index(device_name):
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['name'] == device_name:
            return idx
    return None

class TransparentWindow(QWidget):
    """主窗口类，实现实时字幕显示功能"""
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        # 应用设置存储
        self.settings = QSettings('SNTube', 'SNTrealtimeSubtitles')
        # 音频设备设置
        self.default_input_device_idx = sd.default.device[0]  # 默认输入设备
        self.vac_input_device_idx = find_device_index('Line 1 (Virtual Audio Cable)')  # VAC设备
        self.input_device_idx = self.default_input_device_idx  # 当前使用的设备
        self.is_vac_mode = False  # 是否VAC模式
        # 线程相关
        self.speech_thread = None  # 语音识别线程
        self.wide_char_thread = None  # 宽字符转换线程
        # 字幕缓冲区
        self.buffer = []
        self.counter = 0
        # 语音识别参数
        self.selected_language = 'auto'  # 识别语言
        self.textnorm = False  # 是否启用标点恢复
        self.chunk_size = 10  # 语音块大小
        self.padding = 8  # 填充大小
        self.beam_size = 3  # beam搜索大小
        self.speech_pad_ms = 300  # 语音填充时间(毫秒)
        self.threshold = 0.3  # VAD阈值
        self.min_silence_duration_ms = 300  # 最小静音持续时间(毫秒)
        # 字体设置
        self.font_name = "Arial"  # 默认字体
        self.font_size = 14  # 默认字号
        self.font = QFont(self.font_name, self.font_size)
        self.font.setBold(True)  # 默认加粗
        # 窗口设置
        self.Window_Width = 1000  # 窗口宽度
        self.dragPosition = None  # 拖拽位置
        self.is_hidden = False  # 是否隐藏控制按钮
        self.is_hiddenBG = False  # 是否隐藏背景
        self.alignment = Qt.AlignLeft  # 文本对齐方式
        # 背景相关
        self.font_settings_window = None  # 字体设置窗口
        self.bg_window = None  # 背景窗口
        self.bg_movie = None  # 背景动画(GIF)
        # 初始化流程
        self.initUI()  # 先初始化UI控件
        self.loadSettings()  # 然后加载设置
        self.updateFontSizeInput()  # 更新字号输入框
        self.updateWidthInput()  # 更新宽度滑块
        self.adjustSize()  # 调整窗口大小(更新布局)
        self.restartSpeechThread()  # 启动语音识别线程

    def initUI(self):
        """初始化用户界面"""
        # 打开加载窗口
        self.open_new_window()
        # 初始化背景窗口
        self.bg_window = QWidget()
        self.bg_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.bg_window.setAttribute(Qt.WA_TranslucentBackground)
        self.bg_window.setWindowOpacity(BG_WINDOW_OPACITY)
        # 设置背景窗口鼠标事件
        self.bg_window.dragPosition = None
        self.bg_window.mousePressEvent = self.bgMousePressEvent
        self.bg_window.mouseMoveEvent = self.bgMouseMoveEvent
        # 设置背景窗口右键菜单
        self.bg_window.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bg_window.customContextMenuRequested.connect(lambda pos: self.showContextMenu(pos, self.bg_window))
        # 主窗口基本设置
        self.setWindowTitle('Streaming Captions')
        self.resize(self.Window_Width, 100)
        self.setWindowIcon(QIcon('SimplePage/SC_SNTube.ico'))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        self.setAttribute(Qt.WA_DeleteOnClose)
        # 初始化字幕标签
        self.label = QLabel('等待连接', self)
        font = QFont(self.font_name, self.font_size)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white;")
        self.label.setAlignment(self.alignment)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        self.label.setFixedWidth(self.Window_Width)
        # 最小化按钮
        self.minimize_btn = QPushButton('-')
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.minimize_btn.setStyleSheet("""
            QPushButton { 
                color: white; 
                background-color: black; 
                border: none; 
                border-radius: 5px; 
            }
            QPushButton:hover { 
                background-color: lightgray; 
            }
        """)
        # 关闭按钮
        self.close_btn = QPushButton('×')
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("""
            QPushButton { 
                color: white; 
                background-color: black; 
                border: none; 
                border-radius: 5px; 
            }
            QPushButton:hover { 
                background-color: lightgray; 
            }
        """)
        # 字号设置控件
        self.font_size_label = QLabel('字号')
        self.font_size_label.setStyleSheet("color: gray;")
        self.font_size_input = QLineEdit(str(self.font_size))
        self.font_size_input.setFixedSize(50, 20)
        self.font_size_input.setStyleSheet("""
            QLineEdit { 
                background-color: black; 
                color: gray; 
                border: 1px solid gray; 
                border-radius: 5px; 
                padding: 1px 18px 1px 3px; 
            }
        """)
        self.font_size_input.returnPressed.connect(self.onFontSizeChange)
        self.font_size_input.setFocusPolicy(Qt.ClickFocus)
        # 语言选择下拉框
        self.language_combobox = QComboBox()
        self.language_combobox.addItem('自动', 'auto')
        self.language_combobox.addItem('普通话', 'zh')
        self.language_combobox.addItem('英语', 'en')
        self.language_combobox.addItem('日语', 'ja')
        self.language_combobox.addItem('韩语', 'ko')
        self.language_combobox.addItem('粤语', 'yue')
        self.language_combobox.currentIndexChanged.connect(self.onLanguageChange)
        self.language_combobox.setFixedHeight(20)
        self.language_combobox.setStyleSheet("""
            QComboBox { 
                background-color: black; 
                color: gray; 
                border: 1px solid gray; 
                border-radius: 5px; 
                padding: 1px 18px 1px 3px; 
            }
            QComboBox::drop-down { 
                subcontrol-origin: padding; 
                subcontrol-position: top right; 
                border-top-right-radius: 3px; 
                border-bottom-right-radius: 3px; 
            }
            QComboBox QAbstractItemView { 
                border: 1px solid gray; 
                background-color: black; 
                color: white; 
                selection-background-color: darkgray; 
            }
        """)
        # 设备模式切换按钮
        self.device_switch_btn = QPushButton('麦克风模式ON')
        self.device_switch_btn.setFixedHeight(20)
        self.device_switch_btn.clicked.connect(self.toggleDeviceMode)
        self.device_switch_btn.setStyleSheet("""
            QPushButton { 
                color: green; 
                background-color: black; 
                border: none; 
                border-radius: 5px; 
            }
            QPushButton:hover { 
                background-color: lightgray; 
            }
        """)
        # 窗口宽度滑块
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setMinimum(500)
        self.width_slider.setMaximum(2000)
        self.width_slider.setValue(self.Window_Width)
        self.width_slider.setTickInterval(100)
        self.width_slider.setTickPosition(QSlider.NoTicks)
        self.width_slider.valueChanged.connect(self.onWidthChange)
        self.width_slider.setStyleSheet("""
            QSlider::handle:horizontal {
                background: green;
                width: 9px;
                height: 18px;
                margin: -8px;
                border-radius: 5px;
            }
        """)

        # 主布局设置
        layout = QVBoxLayout()
        layout.addWidget(self.label)  # 添加字幕标签
        layout.addStretch(1)  # 添加弹性空间
        # 控制按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.width_slider)  # 宽度滑块
        btn_layout.addStretch(1)  # 弹性空间
        btn_layout.addWidget(self.font_size_label)  # 字号标签
        btn_layout.addWidget(self.font_size_input)  # 字号输入框
        btn_layout.addWidget(self.language_combobox)  # 语言选择框
        btn_layout.addWidget(self.device_switch_btn)  # 设备切换按钮
        btn_layout.addWidget(self.minimize_btn)  # 最小化按钮
        btn_layout.addWidget(self.close_btn)  # 关闭按钮

        layout.addLayout(btn_layout)  # 将按钮布局添加到主布局

        self.setLayout(layout)  # 设置主窗口布局

        # 右键菜单
        self.context_menu = QMenu(self)
        self.toggle_lock_action = QAction("锁定界面", self)
        self.toggle_lock_action.triggered.connect(self.toggleLockInterface)
        self.toggle_lock_action.setShortcut(QKeySequence('Ctrl+0'))
        self.toggle_visibility_action = QAction("隐藏界面", self)
        self.toggle_visibility_action.triggered.connect(self.toggleVisibility)
        self.toggle_visibility_action.setShortcut(QKeySequence('Alt+1'))
        self.toggle_BG_action = QAction("隐藏背景", self)
        self.toggle_BG_action.triggered.connect(self.toggleBG)
        self.toggle_BG_action.setShortcut(QKeySequence('Alt+2'))
        self.toggle_TextNorm_action = QAction("标点恢复", self)
        self.toggle_TextNorm_action.triggered.connect(self.toggleTextNorm)
        self.toggle_TextNorm_action.setShortcut(QKeySequence('Alt+3'))
        self.toggle_alignment_action = QAction("文本靠左", self)
        self.toggle_alignment_action.triggered.connect(self.toggleAlignment)
        self.toggle_alignment_action.setShortcut(QKeySequence('Alt+4'))
        self.font_settings_action = QAction("字体设置", self)
        self.font_settings_action.triggered.connect(self.openFontSettings)
        self.font_settings_action.setShortcut(QKeySequence('Alt+5'))
        self.move_to_cursor_action = QAction("移动到光标位置", self)
        self.move_to_cursor_action.triggered.connect(self.moveToCursorPosition)
        self.move_to_cursor_action.setShortcut(QKeySequence('Ctrl+9'))
        self.minimize_action = QAction("最小化", self)
        self.minimize_action.triggered.connect(self.showMinimized)
        self.minimize_action.setShortcut(QKeySequence('Ctrl+`'))
        self.close_action = QAction("关闭", self)
        self.close_action.triggered.connect(self.close)
        self.close_action.setShortcut(QKeySequence('Esc'))

        # 创建背景图片子菜单
        self.bg_menu = QMenu("背景图片", self)
        select_bg_action = QAction("选择背景图片", self)
        select_bg_action.triggered.connect(self.selectBackgroundImage)
        self.bg_menu.addAction(select_bg_action)
        clear_bg_action = QAction("清除背景图片", self)
        clear_bg_action.triggered.connect(self.clearBackgroundImage)
        self.bg_menu.addAction(clear_bg_action)
        bg_options_action = QAction("背景图片设置", self)
        bg_options_action.triggered.connect(self.showBackgroundSettings)
        self.bg_menu.addAction(bg_options_action)

        # 添加所有菜单项
        self.context_menu.addMenu(self.bg_menu)
        self.context_menu.addAction(self.toggle_lock_action)
        self.context_menu.addAction(self.toggle_visibility_action)
        self.context_menu.addAction(self.toggle_BG_action)
        self.context_menu.addAction(self.toggle_TextNorm_action)
        self.context_menu.addAction(self.toggle_alignment_action)
        self.context_menu.addAction(self.font_settings_action)
        self.context_menu.addAction(self.move_to_cursor_action)
        self.context_menu.addAction(self.minimize_action)
        self.context_menu.addAction(self.close_action)

        # 设置全局快捷键
        shortcut1 = QShortcut(QKeySequence('Ctrl+0'), self)
        shortcut1.setContext(Qt.ApplicationShortcut)
        shortcut1.activated.connect(self.toggle_lock_action.trigger)
        
        shortcut2 = QShortcut(QKeySequence('Alt+1'), self)
        shortcut2.setContext(Qt.ApplicationShortcut)
        shortcut2.activated.connect(self.toggle_visibility_action.trigger)
        
        shortcut3 = QShortcut(QKeySequence('Alt+2'), self)
        shortcut3.setContext(Qt.ApplicationShortcut)
        shortcut3.activated.connect(self.toggle_BG_action.trigger)
        
        shortcut4 = QShortcut(QKeySequence('Alt+3'), self)
        shortcut4.setContext(Qt.ApplicationShortcut)
        shortcut4.activated.connect(self.toggle_TextNorm_action.trigger)
        
        shortcut5 = QShortcut(QKeySequence('Alt+4'), self)
        shortcut5.setContext(Qt.ApplicationShortcut)
        shortcut5.activated.connect(self.toggle_alignment_action.trigger)
        
        shortcut6 = QShortcut(QKeySequence('Alt+5'), self)
        shortcut6.setContext(Qt.ApplicationShortcut)
        shortcut6.activated.connect(self.font_settings_action.trigger)
        
        shortcut7 = QShortcut(QKeySequence('Ctrl+`'), self)
        shortcut7.setContext(Qt.ApplicationShortcut)
        shortcut7.activated.connect(self.minimize_action.trigger)
        
        shortcut8 = QShortcut(QKeySequence('Esc'), self)
        shortcut8.setContext(Qt.ApplicationShortcut)
        shortcut8.activated.connect(self.close_action.trigger)
        
        menu_key_shortcut = QShortcut(QKeySequence('Menu'), self)
        menu_key_shortcut.setContext(Qt.ApplicationShortcut)
        menu_key_shortcut.activated.connect(self.showContextMenu)
        
        copy_shortcut = QShortcut(QKeySequence('Ctrl+C'), self)
        copy_shortcut.setContext(Qt.ApplicationShortcut)
        copy_shortcut.activated.connect(self.copyLabelContent)

        move_shortcut = QShortcut(QKeySequence('Ctrl+9'), self)
        move_shortcut.setContext(Qt.ApplicationShortcut)
        move_shortcut.activated.connect(self.moveToCursorPosition)

    # 加载动画
    def open_new_window(self):
        """
        # 编译后防止重复运行
        multiprocessing.freeze_support()
        """
        loading_window = Process(target=run_loading_window)
        loading_window.start()

    def showContextMenu(self, pos=None, sender=None):
        # 统一使用主窗口的context_menu
        if sender == self.bg_window:
            pos = self.bg_window.mapToGlobal(pos)
            self.raise_()  # 确保主窗口在最前
            self.context_menu.exec_(pos)
        else:
            # 获取鼠标指针的位置
            pos = self.mapFromGlobal(self.cursor().pos())
            # 显示右键菜单
            self.raise_()  # 确保主窗口在最前
            self.context_menu.exec_(self.mapToGlobal(pos))

    def showBackgroundSettings(self):
        """显示背景图片设置窗口"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                    QLabel, QSlider, QSpinBox, QDoubleSpinBox,
                                    QSpacerItem, QSizePolicy)

        dialog = QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setWindowTitle("背景图片设置")
        dialog.setFixedSize(350, 200)

        layout = QVBoxLayout()
        layout.setSpacing(15)  # 增加行间距

        # 缩放系数设置
        scale_layout = QHBoxLayout()
        scale_label = QLabel("缩放系数 (≥0.01):")
        scale_input = QDoubleSpinBox()
        scale_input.setMinimum(0.01)
        scale_input.setValue(SCALE_FACTOR)
        scale_input.setSingleStep(0.01)
        scale_input.setDecimals(2)
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(scale_input)

        # 横向偏移设置
        offset_x_layout = QHBoxLayout()
        offset_x_label = QLabel("横向偏移:")
        offset_x_spin = QSpinBox()
        offset_x_spin.setRange(-2000, 2000)
        offset_x_spin.setValue(WINDOW_OFFSET_X)
        offset_x_layout.addWidget(offset_x_label)
        offset_x_layout.addWidget(offset_x_spin)

        # 纵向偏移设置
        offset_y_layout = QHBoxLayout()
        offset_y_label = QLabel("纵向偏移:")
        offset_y_spin = QSpinBox()
        offset_y_spin.setRange(-2000, 2000)
        offset_y_spin.setValue(WINDOW_OFFSET_Y)
        offset_y_layout.addWidget(offset_y_label)
        offset_y_layout.addWidget(offset_y_spin)

        # 不透明度设置
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("不透明度:")
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(1, 100)
        opacity_slider.setValue(int(BG_WINDOW_OPACITY * 100))
        opacity_value = QLabel(f"{int(BG_WINDOW_OPACITY * 100)}%")
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(opacity_slider)
        opacity_layout.addWidget(opacity_value)

        # 连接信号
        opacity_slider.valueChanged.connect(
            lambda v: opacity_value.setText(f"{v}%"))

        # 添加更新
        scale_input.valueChanged.connect(
            lambda v: self.updateBackgroundSettings(v, offset_x_spin.value(), offset_y_spin.value(), opacity_slider.value()/100))
        offset_x_spin.valueChanged.connect(
            lambda v: self.updateBackgroundSettings(scale_input.value(), v, offset_y_spin.value(), opacity_slider.value()/100))
        offset_y_spin.valueChanged.connect(
            lambda v: self.updateBackgroundSettings(scale_input.value(), offset_x_spin.value(), v, opacity_slider.value()/100))
        opacity_slider.valueChanged.connect(
            lambda v: self.bg_window.setWindowOpacity(v/100))

        # 添加到主布局
        layout.addLayout(scale_layout)
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(offset_x_layout)
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(offset_y_layout)
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(opacity_layout)

        dialog.setLayout(layout)
        dialog.exec_()
        # 确保在关闭对话框时保存最终的不透明度设置
        self.updateBackgroundSettings(
            scale_input.value(), 
            offset_x_spin.value(), 
            offset_y_spin.value(), 
            opacity_slider.value()/100
        )

    def updateBackgroundSettings(self, scale, offset_x, offset_y, opacity):
        """实时更新背景图片设置"""
        global SCALE_FACTOR, WINDOW_OFFSET_X, WINDOW_OFFSET_Y, BG_WINDOW_OPACITY

        SCALE_FACTOR = scale
        WINDOW_OFFSET_X = offset_x
        WINDOW_OFFSET_Y = offset_y
        BG_WINDOW_OPACITY = opacity

        if self.bg_window:
            self.bg_window.setWindowOpacity(BG_WINDOW_OPACITY)
            self.setBackgroundImage(self.bg_path)

    def selectBackgroundImage(self):
        """打开文件选择器选择背景图片"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择背景图片", 
            "SimplePage", 
            "图片文件 (*.gif *.png *.jpg *.jpeg)"
        )
        if file_path:
            self.setBackgroundImage(file_path)

    def clearBackgroundImage(self):
        """清除当前背景图片"""
        self.setBackgroundImage(None)
        self.bg_path = ""

    def setBackgroundImage(self, file_path=None):
        """设置或清除背景图片
        参数:
            file_path: 背景图片路径，如果为None则清除背景
        功能:
            1. 支持GIF和静态图片(PNG/JPG等)
            2. 自动应用缩放系数和偏移量
            3. 保持与主窗口的位置关系
            4. 处理鼠标事件和右键菜单
        """
        # 清理现有背景窗口
        if self.bg_window:
            self.bg_window.close()
            self.bg_window = None
            self.bg_movie = None

        # 清除背景路径
        if file_path is None:
            self.bg_path = ""
            return

        # 设置新背景图片
        try:
            # 保存背景图片路径
            self.bg_path = file_path

            # 创建新的背景窗口
            self.bg_window = QWidget()
            self.bg_window.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.WindowStaysOnTopHint | 
                Qt.Tool
            )
            self.bg_window.setAttribute(Qt.WA_TranslucentBackground)
            self.bg_window.setWindowOpacity(BG_WINDOW_OPACITY)

            # 创建背景标签用于显示图片
            bg_label = QLabel(self.bg_window)

            # 处理GIF动画
            if file_path.lower().endswith('.gif'):
                self.bg_movie = QMovie(file_path)
                bg_label.setMovie(self.bg_movie)
                self.bg_movie.start()

                # 等待GIF加载完成
                while not self.bg_movie.frameCount():
                    QApplication.processEvents()

                img_size = self.bg_movie.frameRect().size()
            else:
                # 处理静态图片
                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    raise ValueError("无法加载图片文件")

                bg_label.setPixmap(pixmap)
                img_size = pixmap.size()

            # 应用缩放
            bg_label.setScaledContents(True)
            scaled_size = QSize(
                int(img_size.width() * SCALE_FACTOR),
                int(img_size.height() * SCALE_FACTOR))
            self.bg_window.resize(scaled_size)
            bg_label.resize(scaled_size)

            # 设置窗口位置(保持与主窗口的偏移关系)
            self.bg_window.move(
                self.x() - int(WINDOW_OFFSET_X * SCALE_FACTOR),
                self.y() - int(WINDOW_OFFSET_Y * SCALE_FACTOR))

            # 设置鼠标事件处理
            self.bg_window.dragPosition = None
            self.bg_window.mousePressEvent = self.bgMousePressEvent
            self.bg_window.mouseMoveEvent = self.bgMouseMoveEvent

            # 设置右键菜单
            self.bg_window.setContextMenuPolicy(Qt.CustomContextMenu)
            self.bg_window.customContextMenuRequested.connect(
                lambda pos: self.showContextMenu(pos, self.bg_window))

            # 显示背景窗口并确保主窗口在最前
            self.bg_window.show()
            self.raise_()

        except Exception as e:
            print(f"设置背景图片失败: {str(e)}")
            if self.bg_window:
                self.bg_window.close()
            self.bg_window = None
            self.bg_movie = None
            self.bg_path = ""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.7 if not self.is_hiddenBG else 0)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.NoPen)

        radius = 10

        rect = self.rect()
        painter.drawRoundedRect(rect, radius, radius)

    def toggleLockInterface(self):
        """切换界面锁定状态，控制窗口是否可拖拽"""
        self.is_locked = not hasattr(self, 'is_locked') or not self.is_locked
        self.toggle_lock_action.setText("解锁界面" if self.is_locked else "锁定界面")

        # 使用Windows API设置鼠标穿透
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020

        if self.is_locked:
            # 设置主窗口
            hwnd = self.winId().__int__()
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, 
                ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_TRANSPARENT)

            # 设置背景窗口
            if self.bg_window:
                bg_hwnd = self.bg_window.winId().__int__()
                ctypes.windll.user32.SetWindowLongW(bg_hwnd, GWL_EXSTYLE,
                    ctypes.windll.user32.GetWindowLongW(bg_hwnd, GWL_EXSTYLE) | WS_EX_TRANSPARENT)
        else:
            # 恢复主窗口
            hwnd = self.winId().__int__()
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & ~WS_EX_TRANSPARENT)

            # 恢复背景窗口
            if self.bg_window:
                bg_hwnd = self.bg_window.winId().__int__()
                ctypes.windll.user32.SetWindowLongW(bg_hwnd, GWL_EXSTYLE,
                    ctypes.windll.user32.GetWindowLongW(bg_hwnd, GWL_EXSTYLE) & ~WS_EX_TRANSPARENT)

        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        """处理主窗口鼠标按下事件
        功能:
            1. 左键按下时记录拖拽位置(如果未锁定)
            2. 右键点击时显示上下文菜单
        """
        if event.button() == Qt.LeftButton and not getattr(self, 'is_locked', False):
            # 记录当前鼠标位置相对于窗口左上角的偏移
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            self.focusNextChild()  # 转移焦点到下一个控件
        elif event.button() == Qt.RightButton:
            # 显示右键菜单
            self.context_menu.exec_(self.mapToGlobal(event.pos()))

    def bgMousePressEvent(self, event: QMouseEvent):
        """处理背景窗口鼠标按下事件
        功能:
            1. 左键按下时记录拖拽位置(如果未锁定)
            2. 确保主窗口保持置顶状态
        """
        if event.button() == Qt.LeftButton and not getattr(self, 'is_locked', False):
            # 记录当前鼠标位置相对于背景窗口左上角的偏移
            self.bg_window.dragPosition = event.globalPos() - self.bg_window.frameGeometry().topLeft()
            event.accept()
            self.focusNextChild()  # 转移焦点到下一个控件
            self.raise_()  # 确保主窗口保持置顶

    def bgMouseMoveEvent(self, event: QMouseEvent):
        """处理背景窗口鼠标移动事件
        功能:
            1. 左键拖动时移动背景窗口
            2. 同步移动主窗口，保持相对位置
            3. 确保主窗口保持置顶状态
        """
        if (event.buttons() == Qt.LeftButton and 
            self.bg_window.dragPosition is not None and 
            not getattr(self, 'is_locked', False)):

            # 计算新位置
            new_pos = event.globalPos() - self.bg_window.dragPosition

            # 移动背景窗口
            self.bg_window.move(new_pos)

            # 同步移动主窗口，保持相对位置(应用缩放系数)
            self.move(
                new_pos.x() + int(WINDOW_OFFSET_X * SCALE_FACTOR),
                new_pos.y() + int(WINDOW_OFFSET_Y * SCALE_FACTOR))

            # 确保主窗口保持置顶
            self.raise_()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理主窗口鼠标移动事件
        功能:
            1. 左键拖动时移动主窗口(如果未锁定)
            2. 同步移动背景窗口，保持相对位置
        """
        if (event.buttons() == Qt.LeftButton and 
            self.dragPosition is not None and 
            not getattr(self, 'is_locked', False)):

            # 计算新位置
            new_pos = event.globalPos() - self.dragPosition

            # 移动主窗口
            self.move(new_pos)

            # 同步移动背景窗口，保持相对位置(应用缩放系数)
            if self.bg_window:
                self.bg_window.move(
                    self.x() - int(WINDOW_OFFSET_X * SCALE_FACTOR),
                    self.y() - int(WINDOW_OFFSET_Y * SCALE_FACTOR))

            event.accept()

    def loadSettings(self):
        """加载应用设置
        功能:
            1. 从QSettings加载所有保存的设置
            2. 初始化窗口位置、大小和样式
            3. 加载语音识别参数
            4. 加载背景图片设置
        """
        # 加载基本设置
        self.textnorm = self.settings.value('textnorm', False, type=bool)
        # 加载窗口位置和大小
        pos = self.settings.value('pos', QPoint(600, 600))
        size = self.settings.value('size', QSize(self.Window_Width, 100))
        self.setGeometry(pos.x(), pos.y(), size.width(), size.height())
        # 加载字体设置
        self.font_name = self.settings.value('font_name', "Arial")
        self.font_size = self.settings.value('font_size', 14, type=int)
        # 加载窗口宽度
        self.Window_Width = self.settings.value('window_width', 1000, type=int)
        # 加载语言和对齐设置
        self.selected_language = self.settings.value('selected_language', 'auto')
        alignment = self.settings.value('alignment', Qt.AlignLeft, type=int)
        # 加载背景图片路径
        self.bg_path = self.settings.value('bg_path', "")
        # 加载背景窗口设置
        global SCALE_FACTOR, WINDOW_OFFSET_X, WINDOW_OFFSET_Y, BG_WINDOW_OPACITY
        SCALE_FACTOR = self.settings.value('scale_factor', 1.0, type=float)
        WINDOW_OFFSET_X = self.settings.value('window_offset_x', 230, type=int)
        WINDOW_OFFSET_Y = self.settings.value('window_offset_y', 85, type=int)
        BG_WINDOW_OPACITY = self.settings.value('bg_window_opacity', 0.9, type=float)
        # 加载语音识别参数
        self.chunk_size = self.settings.value('chunk_size', 10, type=int)
        self.padding = self.settings.value('padding', 8, type=int)
        self.beam_size = self.settings.value('beam_size', 3, type=int)
        self.speech_pad_ms = self.settings.value('speech_pad_ms', 300, type=int)
        self.threshold = self.settings.value('threshold', 0.3, type=float)
        self.min_silence_duration_ms = self.settings.value('min_silence_duration_ms', 300, type=int)

        # 更新UI控件
        self.font = QFont(self.font_name, self.font_size)
        self.font.setBold(True)
        self.label.setFont(self.font)

        self.label.setFixedWidth(self.Window_Width)
        self.width_slider.setValue(self.Window_Width)
        self.resize(self.Window_Width, self.height())
        self.adjustSize()

        # 更新标点恢复按钮
        self.toggle_TextNorm_action.setText("取消标点" if self.textnorm else "标点恢复")

        self.label.setAlignment(Qt.Alignment(alignment))
        self.toggle_alignment_action.setText("文本居中" if alignment == Qt.AlignLeft else "文本靠左")

        # 断开 currentIndexChanged 信号
        self.language_combobox.blockSignals(True)

        # 设置选中的语言
        index = self.language_combobox.findData(self.selected_language)
        if index != -1:
            self.selected_language = self.language_combobox.itemData(index)
            self.language_combobox.setCurrentIndex(index)

        # 重新连接 currentIndexChanged 信号
        self.language_combobox.blockSignals(False)

    def updateFontSizeInput(self):
        self.font_size_input.setText(str(self.font_size))

    def updateWidthInput(self):
        self.width_slider.setValue(self.Window_Width)

    def closeEvent(self, event):
        """窗口关闭事件处理，保存所有设置并清理资源
        功能:
            1. 保存所有用户设置到QSettings
            2. 关闭字体设置窗口(如果打开)
            3. 优雅地停止所有线程
            4. 强制终止任何未响应的线程
            5. 终止加载窗口进程
        """
        # 保存基本设置
        self.settings.setValue('textnorm', self.textnorm)
        self.settings.setValue('pos', self.pos())
        self.settings.setValue('size', self.size())
        # 保存字体相关设置
        self.settings.setValue('font_name', self.font_name)
        self.settings.setValue('font_size', self.font_size)
        self.settings.setValue('window_width', self.Window_Width)
        # 保存语言和对齐设置
        self.settings.setValue('selected_language', self.selected_language)
        self.settings.setValue('alignment', self.label.alignment())
        # 保存语音识别参数
        self.settings.setValue('chunk_size', self.chunk_size)
        self.settings.setValue('padding', self.padding)
        self.settings.setValue('beam_size', self.beam_size)
        self.settings.setValue('speech_pad_ms', self.speech_pad_ms)
        self.settings.setValue('threshold', self.threshold)
        self.settings.setValue('min_silence_duration_ms', self.min_silence_duration_ms)
        # 保存背景图片路径
        if hasattr(self, 'bg_path') and self.bg_path and os.path.exists(self.bg_path):
            self.settings.setValue('bg_path', self.bg_path)
        else:
            self.settings.setValue('bg_path', "")
        # 保存背景窗口设置
        global SCALE_FACTOR, WINDOW_OFFSET_X, WINDOW_OFFSET_Y, BG_WINDOW_OPACITY
        self.settings.setValue('scale_factor', SCALE_FACTOR)
        self.settings.setValue('window_offset_x', WINDOW_OFFSET_X)
        self.settings.setValue('window_offset_y', WINDOW_OFFSET_Y)
        self.settings.setValue('bg_window_opacity', BG_WINDOW_OPACITY)
        # 关闭字体设置窗口(如果打开)
        if self.font_settings_window and self.font_settings_window.isVisible():
            self.font_settings_window.close()

        # 设置5秒超时强制终止线程
        timeout = 5000  # 毫秒

        # 启动定时器
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self.forceTerminateThreads)

        # 优雅地停止线程
        if self.speech_thread is not None:
            self.speech_thread.running = False  # 设置标志位
            self.speech_thread.quit()  # 请求线程退出
        if self.wide_char_thread is not None:
            self.wide_char_thread.quit()

        # 启动定时器，等待线程退出
        timer.start(timeout)

        # 终止加载窗口进程
        if hasattr(self, 'loading_window') and self.loading_window.is_alive():
            self.loading_window.terminate()
            self.loading_window.join()

        event.accept()  # 允许窗口关闭

    def forceTerminateThreads(self):
        # 强制终止 speech_thread
        if self.speech_thread is not None and self.speech_thread.isRunning():
            print("强制终止 speech_thread")
            self.speech_thread.terminate()
            self.speech_thread.wait()

        # 强制终止 wide_char_thread
        if self.wide_char_thread is not None and self.wide_char_thread.isRunning():
            print("强制终止 wide_char_thread")
            self.wide_char_thread.terminate()
            self.wide_char_thread.wait()

    def toggleDeviceMode(self):
        if self.is_vac_mode:
            self.device_switch_btn.setText('麦克风模式ON')
            self.device_switch_btn.setStyleSheet(
                "QPushButton { color: green; background-color: black; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.input_device_idx = self.default_input_device_idx
            self.is_vac_mode = False
        else:
            self.device_switch_btn.setText('VAC模式ON')
            self.device_switch_btn.setStyleSheet(
                "QPushButton { color: blue; background-color: black; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.input_device_idx = self.vac_input_device_idx
            self.is_vac_mode = True
        self.restartSpeechThread()

    def onLanguageChange(self, index):
        self.selected_language = self.language_combobox.itemData(index)
        self.restartSpeechThread()

    def onFontSizeChange(self):
        try:
            new_font_size = int(self.font_size_input.text())
            if new_font_size > 0:
                self.font_size = new_font_size
                self.font = QFont(self.font_name, self.font_size)  # 更新字体名称和大小
                self.font.setBold(True)
                self.label.setFont(self.font)  # 应用更新后的字体
                self.adjustSize()  # 更新布局
                self.focusNextChild()
        except ValueError:
            pass  # 忽略非法输入

    def onWidthChange(self, value):
        self.Window_Width = value
        self.label.setFixedWidth(self.Window_Width)
        self.resize(self.Window_Width, self.height())
        self.updateWidthInput()  # 更新滑动条的值
        self.adjustSize()  # 更新布局

    def restartSpeechThread(self):
        if self.speech_thread is not None:
            self.speech_thread.terminate()
            self.speech_thread.wait()
        self.speech_thread = SpeechRecognitionThread(self.input_device_idx, language=self.selected_language, textnorm=self.textnorm, chunk_size=self.chunk_size, padding=self.padding, beam_size=self.beam_size, speech_pad_ms=self.speech_pad_ms, threshold=self.threshold, min_silence_duration_ms=self.min_silence_duration_ms)
        self.speech_thread.updateTextSignal.connect(self.updateLabelText)
        self.speech_thread.start()
        print(f'以设备索引启动线程: {self.input_device_idx}\n语言: {self.selected_language}\n标点恢复: {self.textnorm}\nchunk_size: {self.chunk_size}\npadding: {self.padding}\nbeam_size: {self.beam_size}\n语音填充时间: {self.speech_pad_ms}\nVAD阈值: {self.threshold}\n最小静音持续时间: {self.min_silence_duration_ms}')

    def updateLabelText(self, text):
        self.label.setText(text)
        self.adjustSize()  # 更新布局
        if self.wide_char_thread is not None:
            self.wide_char_thread.quit()
            self.wide_char_thread.wait()
        self.wide_char_thread = WideCharThread(text, self)
        self.wide_char_thread.start()

    def copyLabelContent(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.label.text())
        self.label.setStyleSheet("color: green;")
        QTimer.singleShot(300, self.restoreLabelColor)

    def restoreLabelColor(self):
        self.label.setStyleSheet("color: white;")

    def toggleVisibility(self):
        self.is_hidden = not self.is_hidden
        self.toggle_visibility_action.setText("显示界面" if self.is_hidden else "隐藏界面")
        self.update()

        for widget in [self.width_slider, self.font_size_label, self.font_size_input, self.language_combobox, self.device_switch_btn, self.minimize_btn, self.close_btn]:
            widget.setVisible(not self.is_hidden)

    def toggleBG(self):
        """切换背景透明度，不影响bg_window窗口"""
        self.is_hiddenBG = not self.is_hiddenBG
        self.toggle_BG_action.setText("显示背景" if self.is_hiddenBG else "隐藏背景")
        self.update()

    def toggleTextNorm(self):
        self.textnorm = not self.textnorm
        self.settings.setValue('textnorm', self.textnorm)
        self.toggle_TextNorm_action.setText("取消标点" if self.textnorm else "标点恢复")
        self.update()
        self.restartSpeechThread()

    def toggleAlignment(self):
        if self.label.alignment() == Qt.AlignLeft:
            self.label.setAlignment(Qt.AlignCenter)
            self.toggle_alignment_action.setText("文本靠左")
        else:
            self.label.setAlignment(Qt.AlignLeft)
            self.toggle_alignment_action.setText("文本居中")
        self.settings.setValue('alignment', self.label.alignment())
        self.adjustSize()

    def openFontSettings(self):
        self.font_settings_window = FontListWidget()
        self.font_settings_window.font_list.itemSelectionChanged.connect(self.setFontName)
        self.font_settings_window.show()

    def setFontName(self):
        selected_items = self.font_settings_window.font_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            self.font_name = item.text()
            self.font = QFont(self.font_name, self.font_size)
            self.font.setBold(True)
            self.label.setFont(self.font)
            self.settings.setValue('font_name', self.font_name)
            self.adjustSize()

    def moveToCursorPosition(self):
        """将窗口移动到当前光标位置(左上角对齐)"""
        cursor_pos = self.cursor().pos()
        self.move(cursor_pos)
        # 同步移动背景窗口，保持左上角对齐(应用放大倍数)
        if self.bg_window:
            self.bg_window.move(
                cursor_pos.x() - int(WINDOW_OFFSET_X * SCALE_FACTOR),
                cursor_pos.y() - int(WINDOW_OFFSET_Y * SCALE_FACTOR))

    def showEvent(self, event):
        """窗口显示事件，用于延迟加载背景图片"""
        super().showEvent(event)
        if hasattr(self, 'bg_path') and self.bg_path and os.path.exists(self.bg_path):
            # 延迟加载背景图片
            bg_label = QLabel(self.bg_window)
            if self.bg_path.lower().endswith('.gif'):
                self.bg_movie = QMovie(self.bg_path)
                bg_label.setMovie(self.bg_movie)
                self.bg_movie.start()

                # 等待GIF加载完成
                while not self.bg_movie.frameCount():
                    QApplication.processEvents()

                img_size = self.bg_movie.frameRect().size()
            else:  # PNG或其他静态图片
                pixmap = QPixmap(self.bg_path)
                bg_label.setPixmap(pixmap)
                img_size = pixmap.size()

            bg_label.setScaledContents(True)
            scaled_size = QSize(
                int(img_size.width() * SCALE_FACTOR),
                int(img_size.height() * SCALE_FACTOR))
            self.bg_window.resize(scaled_size)
            bg_label.resize(scaled_size)

            # 设置窗口位置
            self.bg_window.move(
                self.x() - int(WINDOW_OFFSET_X * SCALE_FACTOR),
                self.y() - int(WINDOW_OFFSET_Y * SCALE_FACTOR))

            self.bg_window.show()

    def changeEvent(self, event):
        """处理窗口状态变化事件"""
        if event.type() == event.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                # 窗口最小化时，隐藏背景窗口
                if self.bg_window:
                    hwnd = self.bg_window.winId().__int__()
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            else:
                # 窗口从最小化恢复时，显示背景窗口
                if self.bg_window:
                    hwnd = self.bg_window.winId().__int__()
                    ctypes.windll.user32.ShowWindow(hwnd, 5)
                    self.bg_window.raise_()
                    self.raise_()

# def start():
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TransparentWindow()
    ex.show()
    sys.exit(app.exec_())

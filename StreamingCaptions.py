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

from io import StringIO
import sys
import os
import sounddevice as sd
import soundfile as sf
from pysilero import VADIterator
from streaming_sensevoice import StreamingSenseVoice
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QSizePolicy, QLineEdit, QSlider, QMenu, QAction
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QPoint, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QMouseEvent, QIcon

class SpeechRecognitionThread(QThread):
    updateTextSignal = pyqtSignal(str)

    # 加载热词增强
    def load_hotwords(self):
        hotwords_file = os.path.join(os.path.dirname(__file__), "hotwords.txt")
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

    def __init__(self, input_device_idx, language="auto", textnorm=False):
        super().__init__()
        settings = QSettings('SNTube', 'SNTrealtimeSubtitles')
        textnorm = settings.value('textnorm', textnorm, type=bool)
        hotwords = self.load_hotwords()
        print(f"加载的热词: {hotwords}")
        self.model = StreamingSenseVoice(language=language, textnorm=textnorm, contexts=hotwords)
        """
        # 原vad参数
        self.vad_iterator = VADIterator(speech_pad_ms=300)
        # 自调vad参数
        self.vad_iterator = VADIterator(speech_pad_ms=300, threshold=0.3, min_silence_duration_ms=400)
        """
        self.vad_iterator = VADIterator(speech_pad_ms=400, threshold=0.3, min_silence_duration_ms=300)
        self.input_device_idx = input_device_idx
        self.running = True

    def run(self):
        devices = sd.query_devices()
        if len(devices) == 0:
            print("没有找到输入设备，请检查设备是否正常连接")
            return
        """
        # 如果不确定自己的设备列表
        print(devices)
        """
        print(f'所用设备: {devices[self.input_device_idx]["name"]}')

        samples_per_read = int(0.1 * 16000)
        with sd.InputStream(channels=1, dtype="float32", samplerate=16000, device=self.input_device_idx) as s:
            while self.running:
                samples, _ = s.read(samples_per_read)
                for speech_dict, speech_samples in self.vad_iterator(samples[:, 0]):
                    if "start" in speech_dict:
                        self.model.reset()
                    is_last = "end" in speech_dict
                    for res in self.model.streaming_inference(speech_samples * 32768, is_last):
                        sf.write("test.wav", self.vad_iterator.speech_samples, 16000)
                        self.updateTextSignal.emit(res["text"])

    def terminate(self):
        self.running = False
        super().terminate()

def find_device_index(device_name):
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['name'] == device_name:
            return idx
    return None

class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('SNTube', 'SNTrealtimeSubtitles')
        self.clipboard_output_enabled = False
        self.default_input_device_idx = sd.default.device[0]
        self.vac_input_device_idx = find_device_index('Line 1 (Virtual Audio Cable)')
        self.input_device_idx = self.default_input_device_idx
        self.is_vac_mode = False
        self.speech_thread = None
        self.buffer = []
        self.counter = 0
        self.selected_language = 'auto'
        self.textnorm = False
        self.font_size = 14
        self.Window_Width = 1000
        self.dragPosition = None
        self.is_hidden = False
        self.is_hiddenBG = False
        self.initUI()
        self.loadSettings()  # 加载设置
        self.updateFontSizeInput()  # 更新字体大小输入框
        self.updateWidthInput()  # 更新滑动条的值
        self.adjustSize()  # 更新布局
        self.restartSpeechThread()

    def initUI(self):
        self.setWindowTitle('Streaming Captions')
        self.resize(self.Window_Width, 100)
        self.setWindowIcon(QIcon('SC_SNTube.ico'))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        
        self.label = QLabel('等待连接', self)
        font = QFont("Arial", self.font_size)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white;")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        self.label.setFixedWidth(self.Window_Width)

        self.minimize_btn = QPushButton('-')
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.minimize_btn.setStyleSheet("QPushButton { color: white; background-color: black; border: none; border-radius: 5px; }"
                                        "QPushButton:hover { background-color: lightgray; }")

        self.close_btn = QPushButton('×')
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("QPushButton { color: white; background-color: black; border: none; border-radius: 5px; }"
                                     "QPushButton:hover { background-color: lightgray; }")

        self.font_size_label = QLabel('字号')
        self.font_size_label.setStyleSheet("color: gray;")

        self.font_size_input = QLineEdit(str(self.font_size))
        self.font_size_input.setFixedSize(50, 20)
        self.font_size_input.setStyleSheet("QLineEdit { background-color: black; color: gray; border: 1px solid gray; border-radius: 5px; padding: 1px 18px 1px 3px; }")
        self.font_size_input.returnPressed.connect(self.onFontSizeChange)
        self.font_size_input.setFocusPolicy(Qt.ClickFocus)  # 设置输入框在点击时获得焦点

        self.language_combobox = QComboBox()
        self.language_combobox.addItem('自动', 'auto')
        self.language_combobox.addItem('普通话', 'zh')
        self.language_combobox.addItem('英语', 'en')
        self.language_combobox.addItem('日语', 'ja')
        self.language_combobox.addItem('韩语', 'ko')
        self.language_combobox.addItem('粤语', 'yue')
        self.language_combobox.currentIndexChanged.connect(self.onLanguageChange)
        self.language_combobox.setFixedHeight(20)
        self.language_combobox.setStyleSheet("QComboBox { background-color: black; color: gray; border: 1px solid gray; border-radius: 5px; padding: 1px 18px 1px 3px; }"
                                             "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; border-top-right-radius: 3px; border-bottom-right-radius: 3px; }"
                                             "QComboBox QAbstractItemView { border: 1px solid gray; background-color: black; color: white; selection-background-color: darkgray; }")

        self.clipboard_output_btn = QPushButton('剪贴板模式')
        self.clipboard_output_btn.setFixedHeight(20)
        self.clipboard_output_btn.setCheckable(True)
        self.clipboard_output_btn.setChecked(True)
        self.clipboard_output_btn.toggled.connect(self.toggleClipboardOutput)
        self.clipboard_output_btn.setStyleSheet(
            "QPushButton { color: gray; background-color: black; border: none; border-radius: 5px; }"
            "QPushButton:hover { background-color: lightgray; }"
            "QPushButton:checked { color: gray; }"
            "QPushButton:not(:checked) { color: green; }"
        )

        self.device_switch_btn = QPushButton('麦克风模式ON')
        self.device_switch_btn.setFixedHeight(20)
        self.device_switch_btn.clicked.connect(self.toggleDeviceMode)
        self.device_switch_btn.setStyleSheet(
            "QPushButton { color: green; background-color: black; border: none; border-radius: 5px; }"
            "QPushButton:hover { background-color: lightgray; }"
        )

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

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addStretch(1)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.width_slider)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.font_size_label)
        btn_layout.addWidget(self.font_size_input)
        btn_layout.addWidget(self.language_combobox)
        btn_layout.addWidget(self.clipboard_output_btn)
        btn_layout.addWidget(self.device_switch_btn)
        btn_layout.addWidget(self.minimize_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

        # 右键菜单
        self.context_menu = QMenu(self)
        self.toggle_visibility_action = QAction("隐藏界面", self)
        self.toggle_visibility_action.triggered.connect(self.toggleVisibility)
        self.toggle_BG_action = QAction("隐藏背景", self)
        self.toggle_BG_action.triggered.connect(self.toggleBG)
        self.toggle_TextNorm_action = QAction("标点恢复", self)
        self.toggle_TextNorm_action.triggered.connect(self.toggleTextNorm)
        self.minimize_action = QAction("最小化", self)
        self.minimize_action.triggered.connect(self.showMinimized)
        self.close_action = QAction("关闭", self)
        self.close_action.triggered.connect(self.close)
        self.context_menu.addAction(self.toggle_visibility_action)
        self.context_menu.addAction(self.toggle_BG_action)
        self.context_menu.addAction(self.toggle_TextNorm_action)
        self.context_menu.addAction(self.minimize_action)
        self.context_menu.addAction(self.close_action)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.7 if not self.is_hiddenBG else 0)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.NoPen)

        radius = 10
        
        rect = self.rect()
        painter.drawRoundedRect(rect, radius, radius)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            self.focusNextChild()  # 失焦输入框
        elif event.button() == Qt.RightButton:
            self.context_menu.exec_(self.mapToGlobal(event.pos()))

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self.dragPosition is not None:
            self.move(event.globalPos() - self.dragPosition)
            event.accept()

    def loadSettings(self):
        self.textnorm = self.settings.value('textnorm', False, type=bool)
        pos = self.settings.value('pos', QPoint(600, 600))
        size = self.settings.value('size', QSize(self.Window_Width, 100))
        font_size = self.settings.value('font_size', 14, type=int)
        window_width = self.settings.value('window_width', 1000, type=int)
        selected_language = self.settings.value('selected_language', 'auto')

        self.setGeometry(pos.x(), pos.y(), size.width(), size.height())
        self.font_size = font_size
        font = QFont("Arial", self.font_size)
        font.setBold(True)
        self.label.setFont(font)

        self.label.setFixedWidth(self.Window_Width)
        self.width_slider.setValue(window_width)
        self.resize(self.Window_Width, self.height())
        self.adjustSize()

        # 断开 currentIndexChanged 信号
        self.language_combobox.blockSignals(True)

        # 设置选中的语言
        index = self.language_combobox.findData(selected_language)
        if index != -1:
            self.selected_language = self.language_combobox.itemData(index)
            self.language_combobox.setCurrentIndex(index)

        # 重新连接 currentIndexChanged 信号
        self.language_combobox.blockSignals(False)

        # 更新标点恢复按钮
        self.toggle_TextNorm_action.setText("取消标点" if self.textnorm else "标点恢复")

    def updateFontSizeInput(self):
        self.font_size_input.setText(str(self.font_size))
    
    def updateWidthInput(self):
        self.width_slider.setValue(self.Window_Width)

    def closeEvent(self, event):
        self.settings.setValue('textnorm', self.textnorm)
        self.settings.setValue('pos', self.pos())
        self.settings.setValue('size', self.size())
        self.settings.setValue('font_size', self.font_size)
        self.settings.setValue('window_width', self.Window_Width)
        self.settings.setValue('selected_language', self.selected_language)

        if self.speech_thread is not None:
            self.speech_thread.terminate()

    def toggleClipboardOutput(self, state):
        if state:
            self.clipboard_output_btn.setStyleSheet(
                "QPushButton { color: gray; background-color: black; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.clipboard_output_enabled = False
        else:
            self.clipboard_output_btn.setStyleSheet(
                "QPushButton { color: green; background-color: black; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.clipboard_output_enabled = True

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
                font = QFont("Arial", self.font_size)
                font.setBold(True)
                self.label.setFont(font)
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
        self.speech_thread = SpeechRecognitionThread(self.input_device_idx, language=self.selected_language, textnorm=self.textnorm)
        self.speech_thread.updateTextSignal.connect(self.updateLabelText)
        self.speech_thread.start()
        print(f'以设备索引启动线程: {self.input_device_idx}, 语言: {self.selected_language}, 标点恢复: {self.textnorm}')

    def updateLabelText(self, text):
        current_text = self.label.text()
        
        if text.startswith(current_text) or current_text == '':
            self.buffer.append(text)
            self.counter += 1
        else:
            if self.buffer:
                self.copyBufferToClipboard()
                self.buffer.clear()
                self.counter = 0
            self.buffer.append(text)
            self.counter = 1
        
        self.label.setText(text)
        memory_file = StringIO()  # 写入内存
        memory_file.write(text)
        print(memory_file.getvalue())  # print出来给hook用

        # 缓存区累计3行，则自动复制到剪贴板，改成1则实时复制(比如用麦克风当字幕)，改成99则只输出同一句话最后一行(搭配luna历史记录使用)
        if self.clipboard_output_enabled and self.counter >= 3:
            self.copyBufferToClipboard()
            self.buffer.clear()
            self.counter = 0

        self.adjustSize()  # 更新布局
    
    def copyBufferToClipboard(self):
        if not self.clipboard_output_enabled:
            return
        
        multi_line_text = '\n'.join(self.buffer)
        clipboard = QApplication.clipboard()
        clipboard.setText(multi_line_text)

    def toggleVisibility(self):
        self.is_hidden = not self.is_hidden
        self.toggle_visibility_action.setText("显示界面" if self.is_hidden else "隐藏界面")
        self.update()

        for widget in [self.width_slider, self.font_size_label, self.font_size_input, self.language_combobox, self.clipboard_output_btn, self.device_switch_btn, self.minimize_btn, self.close_btn]:
            widget.setVisible(not self.is_hidden)

    def toggleBG(self):
        self.is_hiddenBG = not self.is_hiddenBG
        self.toggle_BG_action.setText("显示背景" if self.is_hiddenBG else "隐藏背景")
        self.update()

    def toggleTextNorm(self):
        self.textnorm = not self.textnorm
        self.toggle_TextNorm_action.setText("取消标点" if self.textnorm else "标点恢复")
        self.update()
        self.restartSpeechThread()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TransparentWindow()
    ex.show()
    sys.exit(app.exec_())
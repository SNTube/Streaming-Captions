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

import sys
import sounddevice as sd
from pysilero import VADIterator
from streaming_sensevoice import StreamingSenseVoice
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout, QComboBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QPoint, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QMouseEvent, QIcon

class SpeechRecognitionThread(QThread):
    updateTextSignal = pyqtSignal(str)

    def __init__(self, input_device_idx, language="auto"):
        super().__init__()
        self.model = StreamingSenseVoice(language=language)
        self.vad_iterator = VADIterator(speech_pad_ms=300)
        self.input_device_idx = input_device_idx
        self.running = True

    def run(self):
        devices = sd.query_devices()
        if len(devices) == 0:
            print("No microphone devices found")
            return
        # 如果不确定自己的设备列表，可以取消下行注释
        # print(devices)
        print(f'Use device: {devices[self.input_device_idx]["name"]}')

        samples_per_read = int(0.1 * 16000)
        with sd.InputStream(channels=1, dtype="float32", samplerate=16000,
                            device=self.input_device_idx) as s:
            while self.running:
                samples, _ = s.read(samples_per_read)
                for speech_dict, speech_samples in self.vad_iterator(samples[:, 0]):
                    if "start" in speech_dict:
                        self.model.reset()
                    is_last = "end" in speech_dict
                    for res in self.model.streaming_inference(speech_samples, is_last):
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
        self.loadSettings()
        self.initUI()
        self.clipboard_output_enabled = True
        self.default_input_device_idx = sd.default.device[0]
        self.vac_input_device_idx = find_device_index('Line 1 (Virtual Audio Cable)')
        self.input_device_idx = self.default_input_device_idx
        self.is_vac_mode = False
        self.speech_thread = None
        self.buffer = []
        self.counter = 0
        self.selected_language = 'auto'
        self.restartSpeechThread()

    def initUI(self):
        self.setWindowTitle('Streaming Captions')
        self.resize(1000, 100)
        self.setWindowIcon(QIcon('SC_SNTube.ico'))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        self.label = QLabel('等待连接', self)
        font = QFont("Arial", 14)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white;")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        self.minimize_btn = QPushButton('-')
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.minimize_btn.setStyleSheet("QPushButton { color: black; background-color: white; border: none; border-radius: 5px; }"
                                        "QPushButton:hover { background-color: lightgray; }")

        self.close_btn = QPushButton('×')
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("QPushButton { color: black; background-color: white; border: none; border-radius: 5px; }"
                                     "QPushButton:hover { background-color: lightgray; }")

        # 下拉框用于选择语言
        self.language_combobox = QComboBox()
        self.language_combobox.addItem('自动', 'auto')
        self.language_combobox.addItem('普通话', 'zh')
        self.language_combobox.addItem('英语', 'en')
        self.language_combobox.addItem('日语', 'ja')
        self.language_combobox.addItem('韩语', 'ko')
        self.language_combobox.addItem('粤语', 'yue')
        self.language_combobox.currentIndexChanged.connect(self.onLanguageChange)
        self.language_combobox.setFixedHeight(20)

        self.clipboard_output_btn = QPushButton('剪贴板模式')
        self.clipboard_output_btn.setFixedHeight(20)
        self.clipboard_output_btn.setCheckable(True)
        self.clipboard_output_btn.setChecked(True)
        self.clipboard_output_btn.toggled.connect(self.toggleClipboardOutput)
        self.clipboard_output_btn.setStyleSheet(
            "QPushButton { color: green; background-color: white; border: none; border-radius: 5px; }"
            "QPushButton:hover { background-color: lightgray; }"
            "QPushButton:checked { color: green; }"
            "QPushButton:not(:checked) { color: gray; }"
        )

        self.device_switch_btn = QPushButton('麦克风模式ON')
        self.device_switch_btn.setFixedHeight(20)
        self.device_switch_btn.clicked.connect(self.toggleDeviceMode)
        self.device_switch_btn.setStyleSheet(
            "QPushButton { color: green; background-color: white; border: none; border-radius: 5px; }"
            "QPushButton:hover { background-color: lightgray; }"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addStretch(1)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.language_combobox)
        btn_layout.addWidget(self.clipboard_output_btn)
        btn_layout.addWidget(self.device_switch_btn)
        btn_layout.addWidget(self.minimize_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.7)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.NoPen)

        radius = 10
        
        rect = self.rect()
        painter.drawRoundedRect(rect, radius, radius)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.dragPosition)
            event.accept()

    def loadSettings(self):
        pos = self.settings.value('pos', QPoint(600, 600))
        size = self.settings.value('size', QSize(1000, 100))
        self.setGeometry(pos.x(), pos.y(), size.width(), size.height())

    def closeEvent(self, event):
        self.settings.setValue('pos', self.pos())
        self.settings.setValue('size', self.size())
        if self.speech_thread is not None:
            self.speech_thread.terminate()

    def toggleClipboardOutput(self, state):
        if state:
            self.clipboard_output_btn.setStyleSheet(
                "QPushButton { color: green; background-color: white; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.clipboard_output_enabled = True
        else:
            self.clipboard_output_btn.setStyleSheet(
                "QPushButton { color: gray; background-color: white; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.clipboard_output_enabled = False

    def toggleDeviceMode(self):
        if self.is_vac_mode:
            self.device_switch_btn.setText('麦克风模式ON')
            self.device_switch_btn.setStyleSheet(
                "QPushButton { color: green; background-color: white; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.input_device_idx = self.default_input_device_idx
            self.is_vac_mode = False
        else:
            self.device_switch_btn.setText('VAC模式ON')
            self.device_switch_btn.setStyleSheet(
                "QPushButton { color: blue; background-color: white; border: none; border-radius: 5px; }"
                "QPushButton:hover { background-color: lightgray; }"
            )
            self.input_device_idx = self.vac_input_device_idx
            self.is_vac_mode = True
        self.restartSpeechThread()

    def onLanguageChange(self, index):
        self.selected_language = self.language_combobox.itemData(index)
        self.restartSpeechThread()

    def restartSpeechThread(self):
        if self.speech_thread is not None:
            self.speech_thread.terminate()
            self.speech_thread.wait()
        self.speech_thread = SpeechRecognitionThread(self.input_device_idx, language=self.selected_language)
        self.speech_thread.updateTextSignal.connect(self.updateLabelText)
        self.speech_thread.start()
        print(f'Started thread with device index: {self.input_device_idx} and language: {self.selected_language}')

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
        
        if self.clipboard_output_enabled and self.counter >= 3:
            self.copyBufferToClipboard()
            self.buffer.clear()
            self.counter = 0
    
    def copyBufferToClipboard(self):
        if not self.clipboard_output_enabled:
            return
        
        multi_line_text = '\n'.join(self.buffer)
        clipboard = QApplication.clipboard()
        clipboard.setText(multi_line_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TransparentWindow()
    ex.show()
    sys.exit(app.exec_())
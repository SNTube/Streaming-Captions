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
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget
from PyQt5.QtGui import QFontDatabase, QIcon

class FontListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowIcon(QIcon('SimplePage/SC_SNTube.ico'))
        self.setWindowTitle('字体设置')
        self.setGeometry(100, 100, 400, 600)

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        layout = QVBoxLayout()
        self.font_list = QListWidget(self)
        layout.addWidget(self.font_list)
        self.setLayout(layout)
        self.loadFonts()

    def loadFonts(self):
        font_db = QFontDatabase()
        fonts = font_db.families()
        fonts.sort()

        for font in fonts:
            self.font_list.addItem(font)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = FontListWidget()
    ex.show()
    sys.exit(app.exec_())
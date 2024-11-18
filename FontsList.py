import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget, QLabel
from PyQt5.QtGui import QFontDatabase, QIcon

class FontListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowIcon(QIcon('SC_SNTube.ico'))
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
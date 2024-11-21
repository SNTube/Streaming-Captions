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

import os
import sys
import requests
import random
import mimetypes
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QPainter, QPixmap, QColor, QPainterPath, QLinearGradient, QIcon, QMovie
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

class LoadingWindow(QDialog):
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(QIcon('SimplePage/SC_SNTube.ico'))
        self.setWindowTitle('Streaming Captions启动中')
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 清理旧的临时图片文件
        self.cleanup_temp_images()

        # 尝试从文件读取图片链接或API链接
        self.image_path = self.load_image_from_file()
        if not self.image_path:
            # 如果文件中没有链接，尝试加载本地图片
            self.image_path = self.get_random_image_path("SimplePage/LoadImg/load")
            if not self.image_path:
                # 如果本地图片也不存在，终止进程
                sys.exit("No image found and process terminated.")
        
        self.is_gif = self.image_path.lower().endswith('.gif')
        
        if self.is_gif:
            self.movie = QMovie(self.image_path)
            self.movie.frameChanged.connect(self.update)
            self.movie.start()
        else:
            self.pixmap = QPixmap(self.image_path)
        
        # 计算窗口宽度
        self.height = 400
        if self.is_gif:
            self.width = int(self.height * (self.movie.frameRect().width() / self.movie.frameRect().height())) + 150
        else:
            self.width = int(self.height * (self.pixmap.width() / self.pixmap.height())) + 150  # 增加右侧区域的宽度
        
        # 设置窗口大小
        self.resize(self.width, self.height)
        
        # 居中显示窗口
        screen_geometry = QApplication.desktop().screenGeometry()
        x = (screen_geometry.width() - self.width) // 2
        y = (screen_geometry.height() - self.height) // 2
        self.move(x, y)
        
        # 加载右侧图片并调整大小
        self.side_pixmap = QPixmap("SimplePage/SC_SNTube.ico").scaled(80, 80)
        
        # 初始化透明度
        self.setWindowOpacity(0)
        
        # 创建渐显动画
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(500)  # 渐显时间半秒
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 创建渐隐动画
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(500)  # 渐隐时间半秒
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 连接动画完成信号
        self.fade_in_animation.finished.connect(self.start_timer)
        self.fade_out_animation.finished.connect(self.close)
        
        # 开始渐显动画
        self.fade_in_animation.start()
    
        # 添加定时器，每200毫秒自动获取焦点和置顶
        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self.bring_to_front)
        self.focus_timer.start(200)

    def cleanup_temp_images(self):
        directory = "SimplePage"
        for filename in os.listdir(directory):
            if filename.startswith("temp_image"):
                file_path = os.path.join(directory, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

    def load_image_from_file(self):
        try:
            with open("SimplePage/load_url.txt", "r") as file:
                lines = file.readlines()  # 读取所有行
            if lines:
                url = random.choice(lines).strip()  # 随机选择一行并去除两端空白字符
                return self.load_image_from_url(url)
            return None
        except FileNotFoundError:
            return None

    def load_image_from_url(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            # 从响应头中获取图片的MIME类型
            content_type = response.headers.get('Content-Type')
            # 如果没有MIME类型，尝试从URL中获取
            if not content_type:
                content_type, _ = mimetypes.guess_type(url)
            # 根据MIME类型确定文件扩展名
            extension = mimetypes.guess_extension(content_type)
            # 如果没有MIME类型或者不支持的类型，返回None
            if not extension:
                print("No MIME type found or unsupported image format.")
                return None
            # 保存图片到SimplePage目录下，文件名为temp_image加上扩展名
            temp_image_path = os.path.join("SimplePage", f"temp_image{extension}")
            with open(temp_image_path, "wb") as f:
                f.write(response.content)
            return temp_image_path
        except requests.RequestException as e:
            print(f"Failed to load image from URL: {e}")
            return None

    def get_random_image_path(self, base_path):
        directory = os.path.dirname(base_path)
        filename = os.path.basename(base_path)
        images = [f for f in os.listdir(directory) if f.startswith(filename)]
        if images:
            return os.path.join(directory, random.choice(images))
        raise FileNotFoundError(f"No image found at {base_path}")
        
    def start_timer(self):
        # 3秒后开始渐隐动画
        QTimer.singleShot(3000, self.fade_out_animation.start)

    def bring_to_front(self):
        # 获取焦点和置顶
        # self.activateWindow()
        self.raise_()
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 绘制圆角矩形背景
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        radius = 10
        path.addRoundedRect(0, 0, self.width - 150, self.height, radius, radius)  # 主体部分
        painter.fillPath(path, QColor(255, 255, 255))
        
        # 使用路径裁剪背景图片
        painter.save()
        painter.setClipPath(path)
        if self.is_gif:
            current_frame = self.movie.currentPixmap()
            painter.drawPixmap(0, 0, self.width - 150, self.height, current_frame)
        else:
            painter.drawPixmap(0, 0, self.width - 150, self.height, self.pixmap)
        painter.restore()
        
        # 创建一个线性渐变
        gradient = QLinearGradient(0, self.height - 50, self.width - 150, self.height - 50)
        gradient.setColorAt(0, QColor(0, 0, 0, 255))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        
        # 绘制底部黑色长条
        painter.fillRect(0, self.height - 50, self.width - 150, 40, gradient)
        
        # 打印测试文本
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(10, self.height - 25, "加载中...")
        
        # 绘制右侧半透明背景
        right_path = QPainterPath()
        right_path.addRoundedRect(self.width - 150, 0, 150, self.height, radius, radius)
        painter.fillPath(right_path, QColor(0, 0, 0, 128))
        
        # 计算图片的位置
        top_margin = int(self.height * 0.05)
        left_margin = self.width - 150 + (150 - self.side_pixmap.width()) // 2  # 水平居中
        
        # 绘制右侧图片
        painter.drawPixmap(left_margin, top_margin, self.side_pixmap)
        
        text = "Streaming Captions"
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.width(text)
        text_height = font_metrics.height()

        font = painter.font()
        font.setPointSize(15)
        font.setFamily("Arial")
        painter.setFont(font)

        # 计算旋转后的文本位置
        text_x_rotated = self.width - 150 + (150 - text_height) // 2
        text_y_rotated = self.height - (top_margin + self.side_pixmap.height() + 30 + text_width)

        # 设置字体方向为竖直
        painter.translate(text_x_rotated, text_y_rotated)
        painter.rotate(90)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(0, 0, text)
        painter.rotate(-90)
        painter.translate(-text_x_rotated, -text_y_rotated)

    def closeEvent(self, event):
        super().closeEvent(event)
        # 释放资源，例如停止动画、释放图片等
        if self.is_gif:
            self.movie.stop()
        # 确保窗口关闭后释放所有资源
        self.deleteLater()

# 用于测试 多进程调用时不建立QApplication
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     loading_window = LoadingWindow()
#     loading_window.destroyed.connect(app.quit)
#     loading_window.exec_()

# 多进程调用 建立QApplication
def run_loading_window():
    app = QApplication(sys.argv)
    loading_window = LoadingWindow()
    loading_window.show()
    # 监听加载窗口的关闭事件，并在窗口关闭后退出 QApplication
    loading_window.destroyed.connect(app.quit)
    sys.exit(app.exec_())
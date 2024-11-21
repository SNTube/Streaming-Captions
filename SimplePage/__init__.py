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


from SimplePage.FontsList import FontListWidget

# 阻塞模式
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     loading_window = LoadingWindow()
#     loading_window.exec_()
#     ex = TransparentWindow()
#     ex.show()
#     sys.exit(app.exec_())
from SimplePage.LoadingPage import LoadingWindow

# 多进程模式
    # # 加载动画
    # def open_new_window(self):
    #     loading_window = Process(target=run_loading_window)
    #     loading_window.start()
    # def __init__(self, input_device_idx, language="auto", textnorm=False):
    #     # 先加载动画
    #     self.open_new_window()
    #     # 再载模型
    #     from streaming_sensevoice import StreamingSenseVoice
from SimplePage.LoadingPage import run_loading_window
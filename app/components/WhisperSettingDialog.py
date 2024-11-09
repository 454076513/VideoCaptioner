import os
from pathlib import Path
import subprocess
import shutil
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QProgressBar,
                           QMessageBox, QLabel)
from qfluentwidgets import (ComboBoxSettingCard, MessageBoxBase, 
                          BodyLabel, PushButton, InfoBar, InfoBarPosition,
                          ProgressBar, ComboBox, HyperlinkButton)
from qfluentwidgets import FluentIcon as FIF

from ..common.config import cfg
from ..core.entities import WhisperModelEnum, TranscribeLanguageEnum
from ..config import MODEL_PATH
from ..core.utils.logger import setup_logger
from ..config import CACHE_PATH

logger = setup_logger("whisper_download")

# 定义模型配置
WHISPER_MODELS = [
    {
        "label": "Tiny",
        "value": "ggml-tiny.bin", 
        "size": "77.7 MB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin?download=true"
    },
    {
        "label": "Base",
        "value": "ggml-base.bin",
        "size": "148 MB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base.bin?download=true"
    },
    {
        "label": "Small",
        "value": "ggml-small.bin",
        "size": "488 MB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-small.bin?download=true"
    },
    {
        "label": "Medium",
        "value": "ggml-medium.bin",
        "size": "1.53 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin?download=true"
    },
    {
        "label": "Large(v1)",
        "value": "ggml-large-v1.bin",
        "size": "3.09 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v1.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v1.bin?download=true"
    },
    {
        "label": "Large(v2)",
        "value": "ggml-large-v2.bin",
        "size": "3.09 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin?download=true"
    },
    {
        "label": "Large(v3)",
        "value": "ggml-large-v3.bin",
        "size": "3.09 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
        "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin?download=true"
    },
    {
        "label": "Distil Large(v3)",
        "value": "ggml-distil-large-v3.bin",
        "size": "1.52 GB",
        "downloadLink": "https://huggingface.co/distil-whisper/distil-large-v3-ggml/resolve/main/ggml-distil-large-v3.bin?download=true",
        "mirrorLink": "https://hf-mirror.com/distil-whisper/distil-large-v3-ggml/resolve/main/ggml-distil-large-v3.bin?download=true"
    }
]

class DownloadThread(QThread):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.process = None
        
    def run(self):
        try:
            # 创建缓存下载目录
            temp_dir = CACHE_PATH / "whisper_models"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / os.path.basename(self.save_path)
            
            # 检查是否存在未完成的下载文件
            if temp_file.exists():
                logger.info(f"发现未完成的下载文件: {temp_file}")
            self.progress.emit(0, self.tr("正在连接..."))
            cmd = [
                'aria2c',
                '--show-console-readout=false',
                '--summary-interval=1',
                '-x2',
                '-s2',
                '--connect-timeout=10',  # 连接超时时间10秒
                '--timeout=10',          # 数据传输超时时间10秒
                '--max-tries=2',         # 最大重试次数2次
                '--retry-wait=1',        # 重试等待时间1秒
                '--continue=true',       # 开启断点续传
                '--auto-file-renaming=false',
                '--allow-overwrite=true',
                '--check-certificate=false',
                
                f'--dir={temp_dir}',
                f'--out={temp_file.name}',
                self.url
            ]
            
            logger.info("运行下载命令: %s", " ".join(cmd))
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            while True:
                if self.process.poll() is not None:
                    break
                    
                line = self.process.stdout.readline()
                
                if '[#' in line and ']' in line:
                    try:
                        # 解析类似 "[#40ca1b 2.4MiB/74MiB(3%) CN:2 DL:3.9MiB ETA:18s]" 的格式
                        progress_part = line.split('(')[1].split(')')[0]
                        percent = float(progress_part.strip('%'))
                        
                        # 提取下载速度和剩余时间
                        speed = "0"
                        eta = ""
                        if "DL:" in line:
                            speed = line.split("DL:")[1].split()[0]
                        if "ETA:" in line:
                            eta = line.split("ETA:")[1].split(']')[0]
                        status_msg = f"{self.tr('速度')}: {speed}/s, {self.tr('剩余时间')}: {eta}"
                        self.progress.emit(percent, status_msg)
                    except Exception as e:
                        pass
                        
            if self.process.returncode == 0:
                # 下载完成后移动文件到目标位置
                os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
                shutil.move(str(temp_file), self.save_path)
                self.finished.emit()
            else:
                error = self.process.stderr.read()
                logger.error("下载失败: %s", error)
                self.error.emit(f"{self.tr('下载失败')}: {error}")
                
        except Exception as e:
            logger.error("下载异常: %s", str(e))
            self.error.emit(str(e))
            
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

class DownloadDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setWindowTitle(self.tr('下载模型'))
        self.download_thread = None

    def setup_ui(self):
        self.titleLabel = BodyLabel(self.tr('下载模型'), self)
        
        # 添加模型选择下拉框
        self.model_combo = ComboBox(self)
        self.model_combo.setFixedWidth(300)
        for model in WHISPER_MODELS:
            # 检查模型是否已下载
            model_path = os.path.join(MODEL_PATH, model['value'])
            downloaded = "✓ " if os.path.exists(model_path) else " "
            self.model_combo.addItem(f"{downloaded}{model['label']} ({model['size']})")
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.hide()
        
        # 进度标签
        self.progress_label = BodyLabel()
        self.progress_label.hide()
        
        # 下载按钮
        self.download_button = PushButton(self.tr('下载'), self)
        self.download_button.clicked.connect(self.start_download)
        
        # 添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.model_combo)
        self.viewLayout.addWidget(self.progress_bar)
        self.viewLayout.addWidget(self.progress_label)
        self.viewLayout.addWidget(self.download_button)
        # 设置间距
        self.viewLayout.setSpacing(10)

        # 只显示取消按钮
        self.yesButton.hide()
        self.cancelButton.setText(self.tr('关闭'))
            
    def start_download(self):
        selected_index = self.model_combo.currentIndex()
        model = WHISPER_MODELS[selected_index]
        save_path = os.path.join(MODEL_PATH, model['value'])
        
        # 检查模型文件是否已存在
        if os.path.exists(save_path):
            InfoBar.warning(
                title=self.tr('提示'),
                content=self.tr('模型文件已存在,无需重复下载'),
                parent=self,
                duration=3000
            )
            return
            
        self.progress_bar.show()
        self.progress_label.show()
        self.download_button.setEnabled(False)
        
        self.download_thread = DownloadThread(
            model['mirrorLink'],
            save_path
        )
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()
        
    def update_progress(self, value, status_msg):
        self.progress_bar.setValue(int(value))
        self.progress_label.setText(status_msg)
        
    def download_finished(self):
        InfoBar.success(
            title=self.tr('完成'),
            content=self.tr('模型下载完成!'),
            parent=self,
            duration=3000
        )
        self.download_button.setEnabled(True)
        self.progress_label.hide()
        
    def download_error(self, error):
        InfoBar.error(
            title=self.tr('错误'),
            content=error,
            parent=self,
            duration=3000
        )
        self.download_button.setEnabled(True)
        self.progress_label.hide()
        
    def reject(self):
        if self.download_thread and self.download_thread.isRunning():
            logger.info("关闭下载对话框,终止下载")
            self.download_thread.stop()
        super().reject()

class WhisperSettingDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self.tr('Whisper 设置'), self)
        
        # 创建设置卡片
        self.model_card = ComboBoxSettingCard(
            cfg.whisper_model,
            FIF.ROBOT,
            self.tr('模型'),
            self.tr('选择Whisper模型'),
            [model.value for model in WhisperModelEnum],
            self
        )
        
        self.language_card = ComboBoxSettingCard(
            cfg.transcribe_language,
            FIF.LANGUAGE,
            self.tr('源语言'),
            self.tr('音频的源语言'), 
            [language.value for language in TranscribeLanguageEnum],
            self
        )

        self.buttonLayout = QHBoxLayout()
        # 创建下载模型按钮
        self.downloadButton = PushButton(self.tr('下载模型'), self)
        self.downloadButton.clicked.connect(self.show_download_dialog)
        
        self.openFolderButton = HyperlinkButton(
            f'file:///{MODEL_PATH}',
            self.tr('打开模型文件夹'), 
            self
        )
        self.buttonLayout.addWidget(self.downloadButton)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.openFolderButton)

        # 添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.model_card)
        self.viewLayout.addWidget(self.language_card)
        self.viewLayout.addLayout(self.buttonLayout)

        # 设置按钮文本
        self.yesButton.setText(self.tr('确定'))
        self.yesButton.clicked.connect(self.__onYesButtonClicked)
        self.widget.setMinimumWidth(400)
    
    def show_download_dialog(self):
        download_dialog = DownloadDialog(self)
        download_dialog.show()

    
    def check_whisper_model(self):
        model_type = cfg.whisper_model.value.value
        model_files = list(Path(MODEL_PATH).glob(f"*ggml*{model_type}*.bin"))
        if not model_files:
            logger.error(f"在 {MODEL_PATH} 目录下未找到包含 '{model_type}' 的模型文件")
            return False
        return True
    
    def __onYesButtonClicked(self):
        if self.check_whisper_model():
            self.accept()
            InfoBar.success(
                self.tr("找到模型文件"),
                self.tr("Whisper设置已更新"),
                duration=3000,
                parent=self,
                position=InfoBarPosition.BOTTOM_RIGHT
            )
        else:
            InfoBar.error(
                title=self.tr('错误'),
                content=self.tr('模型文件不存在'),
                parent=self.window(),
                duration=3000,
                position=InfoBarPosition.BOTTOM_RIGHT
            )
import os
import time
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QFormLayout, QComboBox,
                             QFileDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal
from ui_common import STYLE_SHEET, BASE_DIR

class RegisterDialog(QDialog):
    register_attempt = pyqtSignal(str, int, str, str, str, str)

    def __init__(self, server_host, server_port, parent=None):
        super().__init__(parent)
        self.server_host = server_host
        self.server_port = server_port
        self.setWindowTitle("注册")
        self.setFixedSize(350, 380)
        self.setStyleSheet(STYLE_SHEET)

        layout = QFormLayout()
        layout.setSpacing(10)

        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["Base64", "ROT13", "AES", "自定义"])

        avatar_layout = QHBoxLayout()
        self.avatar_edit = QLineEdit()
        self.avatar_edit.setPlaceholderText("点击浏览选择头像")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_avatar)
        avatar_layout.addWidget(self.avatar_edit)
        avatar_layout.addWidget(browse_btn)

        layout.addRow("用户名:", self.username_edit)
        layout.addRow("密码:", self.password_edit)
        layout.addRow("确认密码:", self.confirm_edit)
        layout.addRow("头像:", avatar_layout)
        layout.addRow("编码规则:", self.encoding_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_register_clicked)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red;")
        layout.addRow(self.status_label)

        self.setLayout(layout)

    def browse_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像图片", BASE_DIR,
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            # 确保avatars目录存在
            avatars_dir = os.path.join(BASE_DIR, 'avatars')
            if not os.path.exists(avatars_dir):
                os.makedirs(avatars_dir)
            # 生成新的文件名，使用用户名作为前缀
            username = self.username_edit.text().strip() or 'unknown'
            ext = os.path.splitext(file_path)[1]
            new_filename = f"{username}_{int(time.time())}{ext}"
            new_path = os.path.join(avatars_dir, new_filename)
            # 复制文件到avatars目录
            import shutil
            shutil.copy2(file_path, new_path)
            # 存储相对路径
            relative_path = os.path.join('avatars', new_filename)
            self.avatar_edit.setText(relative_path)

    def on_register_clicked(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        confirm = self.confirm_edit.text().strip()
        encoding = self.encoding_combo.currentText()
        avatar = self.avatar_edit.text().strip() or ""

        if not username or not password:
            QMessageBox.warning(self, "警告", "用户名和密码不能为空")
            return
        if password != confirm:
            QMessageBox.warning(self, "警告", "两次输入的密码不一致")
            return

        self.status_label.setText("正在注册...")
        self.register_attempt.emit(self.server_host, self.server_port,
                                   username, password, encoding, avatar)

    def register_success(self):
        QMessageBox.information(self, "成功", "注册成功，请登录")
        self.accept()

    def register_failed(self, message):
        self.status_label.setText(f"注册失败: {message}")
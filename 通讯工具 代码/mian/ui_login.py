from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal
from ui_common import STYLE_SHEET
import json
import os

class LoginDialog(QDialog):
    login_attempt = pyqtSignal(str, int, str, str)  

    def __init__(self):
        super().__init__()
        self.setWindowTitle("登录")
        self.resize(520, 400)                     # 设置初始大小，4:3比例，适中
        self.setMinimumSize(400, 300)             # 设置最小尺寸，避免界面过小
    
        custom_style = STYLE_SHEET + """
            /* 下拉框样式 */
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 14px;
                background-color: white;
                min-height: 38px;
            }
            QComboBox:hover {
                border: 1px solid #07c160;
            }
            QComboBox:focus {
                border: 1px solid #07c160;
                outline: none;
            }
            /* 下拉按钮样式 */
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #e0e0e0;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            /* 下拉箭头样式 - 使用系统默认箭头 */
            QComboBox::down-arrow {
                width: 20px;
                height: 20px;
            }
            /* 下拉列表样式 */
            QComboBox QAbstractItemView {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #07c160;
                selection-color: white;
                font-size: 16px;  /* 增大字体大小 */
                padding: 5px;
                max-height: 300px;  /* 设置最大高度，显示更多选项 */
            }
            /* 下拉列表项 */
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 30px;
            }
        """
        self.setStyleSheet(custom_style)

        # 主布局
        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.setContentsMargins(30, 30, 30, 30)

        # 标题
        title = QLabel("🔐 信微聊天")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #07c160;")
        layout.addWidget(title)

        # 固定服务器信息提示
        server_info = QLabel("服务器: 127.0.0.1:8000")
        server_info.setAlignment(Qt.AlignCenter)
        server_info.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(server_info)

        # 用户名下拉框
        self.username_combo = QComboBox()
        self.username_combo.setPlaceholderText("选择或输入用户名")
        self.username_combo.setMinimumHeight(38)
        self.username_combo.setEditable(True)
        layout.addWidget(self.username_combo)

        # 密码输入框
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setMinimumHeight(38)
        layout.addWidget(self.password_edit)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        self.login_btn = QPushButton("登录")
        self.register_btn = QPushButton("注册")
        self.login_btn.setMinimumHeight(40)
        self.register_btn.setMinimumHeight(40)
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.register_btn)
        layout.addLayout(btn_layout)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # 加载保存的用户名
        self.load_usernames()

        # 连接信号
        self.login_btn.clicked.connect(self.on_login_clicked)

    def load_usernames(self):
        """加载保存的用户名"""
        config_path = os.path.join(os.path.dirname(__file__), "login_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    usernames = config.get('usernames', [])
                    for username in usernames:
                        self.username_combo.addItem(username)
            except Exception as e:
                print(f"加载用户名失败: {e}")

    def save_username(self, username):
        """保存新的用户名"""
        config_path = os.path.join(os.path.dirname(__file__), "login_config.json")
        
        # 读取现有配置
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {'usernames': []}
        else:
            config = {'usernames': []}
        
        # 确保用户名唯一
        usernames = config.get('usernames', [])
        if username not in usernames:
            usernames.insert(0, username)  # 新用户名放在最前面
            # 最多保存10个用户名
            if len(usernames) > 10:
                usernames = usernames[:10]
        else:
            # 如果用户名已存在，移到最前面
            usernames.remove(username)
            usernames.insert(0, username)
        
        # 保存配置
        config['usernames'] = usernames
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户名失败: {e}")

    def on_login_clicked(self):
        host = "127.0.0.1"
        port = 8000

        username = self.username_combo.currentText().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "警告", "用户名和密码不能为空")
            return

        self.status_label.setText("正在连接服务器...")
        self.login_btn.setEnabled(False)
        self.register_btn.setEnabled(False)

        self.login_attempt.emit(host, port, username, password)

    def login_failed(self, message):
        self.status_label.setText(f"登录失败: {message}")
        self.login_btn.setEnabled(True)
        self.register_btn.setEnabled(True)

    def login_success(self):
        # 保存成功登录的用户名
        username = self.username_combo.currentText().strip()
        if username:
            self.save_username(username)
        self.accept()

    def get_server_address(self):
        return "127.0.0.1", 8000
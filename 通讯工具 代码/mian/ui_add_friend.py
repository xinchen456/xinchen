import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMessageBox)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from ui_common import STYLE_SHEET, resolve_avatar_path, create_round_pixmap, create_default_avatar_icon

class AddFriendDialog(QDialog):
    search_signal = pyqtSignal(str)
    add_friend_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加好友")
        self.setMinimumSize(400, 500)
        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout()

        # 搜索输入框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入用户名关键词")
        self.search_btn = QPushButton("搜索")
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # 搜索结果列表
        self.result_list = QListWidget()
        self.result_list.setIconSize(QSize(40, 40))
        self.result_list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.result_list)

        self.setLayout(layout)

        self.search_btn.clicked.connect(self.on_search)
        self.search_edit.returnPressed.connect(self.on_search)

    def on_search(self):
        keyword = self.search_edit.text().strip()
        if keyword:
            self.search_signal.emit(keyword)

    def update_results(self, users):
        self.result_list.clear()
        for user in users:
            username = user['username']
            avatar_path = user.get('avatar', '')
            item = QListWidgetItem(username)
            real_path = resolve_avatar_path(avatar_path)
            if real_path and os.path.exists(real_path):
                pixmap = QPixmap(real_path)
                if not pixmap.isNull():
                    round_pixmap = create_round_pixmap(pixmap, 40)
                    item.setIcon(QIcon(round_pixmap))
            else:
                item.setIcon(create_default_avatar_icon(40))
            self.result_list.addItem(item)

    def on_item_clicked(self, item):
        username = item.text()
        reply = QMessageBox.question(self, "添加好友", f"确定要添加 {username} 为好友吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.add_friend_signal.emit(username)
            self.accept()
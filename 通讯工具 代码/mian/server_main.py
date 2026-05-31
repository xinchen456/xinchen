import os
import sys
import sqlite3
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDialog, QTableWidgetItem,
                             QMessageBox, QHeaderView, QFormLayout,
                             QLineEdit, QCheckBox, QDialogButtonBox, QListWidgetItem,
                             QComboBox, QStyledItemDelegate, QAbstractItemView,
                             QPushButton, QHBoxLayout, QFileDialog, QVBoxLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QDateTime, QSize, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QColor, QBrush
from PyQt5.QtNetwork import QTcpServer, QHostAddress
from PyQt5 import uic

from server_network import ClientHandler, resolve_avatar_path, make_grayscale

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENCODING_RULES = ["Base64", "ROT13", "AES", "自定义"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('zhujiemian.ui', self)

        central = self.centralwidget
        toolbar = self.toolbarWidget
        user_list = self.userListWidget
        log_edit = self.logTextEdit

        new_layout = QVBoxLayout(central)
        new_layout.setContentsMargins(9, 9, 9, 9)
        new_layout.setSpacing(6)

        self.pushButton.setFixedWidth(80)
        self.pushButton_2.setFixedWidth(80)
        self.spinBox.setFixedWidth(70)
        self.label.setFixedWidth(80)  

        toolbar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        new_layout.addWidget(toolbar)

        user_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        new_layout.addWidget(user_list, 2)

        log_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        new_layout.addWidget(log_edit, 1)

        self.setMinimumSize(600, 400)

        self.init_db()

        self.tcp_server = QTcpServer(self)
        self.tcp_server.newConnection.connect(self.on_new_connection)
        self.online_users = {}
        self.handlers = []
        self.server_running = False
        self.avatar_cache = {}  # 头像缓存

        self.load_online_users()
        self.file_storage_dir = "server_files"
        if not os.path.exists(self.file_storage_dir):
            os.makedirs(self.file_storage_dir)
        self.log("服务器启动就绪")

        self.pushButton.clicked.connect(self.open_user_manage)
        self.pushButton_2.clicked.connect(self.toggle_server)

    def init_db(self):
        """创建数据库和表（必须包含此方法）"""
        self.conn = sqlite3.connect('server.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                avatar TEXT,
                password TEXT NOT NULL,
                encoding_rule TEXT,
                locked INTEGER DEFAULT 0,
                create_time TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                request_time TEXT NOT NULL,
                FOREIGN KEY(from_user) REFERENCES users(username),
                FOREIGN KEY(to_user) REFERENCES users(username)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                PRIMARY KEY (user_id, friend_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(friend_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offline_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offline_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL UNIQUE,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                file_path TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN login_failures INTEGER DEFAULT 0")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_fail_time TEXT")
        except:
            pass
        self.conn.commit()

    def log(self, message):
        """向日志区域添加带时间戳的消息，若窗口已销毁则忽略"""
        try:
            if not self.logTextEdit:
                return
            timestamp = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
            self.logTextEdit.append(f"[{timestamp}] {message}")
        except RuntimeError:
            pass

    def load_online_users(self):
        self.userListWidget.clear()
        item = QListWidgetItem("正在加载用户列表...")
        item.setFlags(Qt.NoItemFlags)
        item.setForeground(QBrush(QColor(150, 150, 150)))
        item.setTextAlignment(Qt.AlignCenter)
        self.userListWidget.addItem(item)
        QTimer.singleShot(10, self._do_load_online_users)

    def _do_load_online_users(self):
        self.userListWidget.clear()
        cursor = self.conn.cursor()
        cursor.execute("SELECT username, avatar FROM users")
        rows = cursor.fetchall()

        if not rows:
            item = QListWidgetItem("暂无用户")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QBrush(QColor(150, 150, 150)))
            item.setTextAlignment(Qt.AlignCenter)
            self.userListWidget.addItem(item)
            return

        for username, avatar_path in rows:
            self._add_user_item(username, avatar_path)

    def _add_user_item(self, username, avatar_path):
        item = QListWidgetItem()
        if username in self.online_users:
            display_text = f"{username} [在线]"
            item.setForeground(QBrush(QColor(0, 150, 0)))
        else:
            display_text = f"{username} [离线]"
            item.setForeground(QBrush(QColor(150, 150, 150)))
        item.setText(display_text)

        # 生成缓存键
        cache_key = f"{avatar_path}_{'online' if username in self.online_users else 'offline'}"
        
        # 检查缓存
        if cache_key in self.avatar_cache:
            icon = self.avatar_cache[cache_key]
        else:
            # 加载头像
            real_path = resolve_avatar_path(avatar_path, BASE_DIR)
            pixmap = QPixmap()
            if real_path:
                # 限制头像大小，提高加载速度
                pixmap.load(real_path)
                if not pixmap.isNull():
                    # 先缩放到合适大小
                    pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            if pixmap.isNull():
                # 创建默认头像
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setBrush(QColor(180, 180, 180))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(2, 2, 60, 60)
                painter.end()

            # 处理离线状态
            if username not in self.online_users:
                pixmap = make_grayscale(pixmap)

            # 缩放到最终大小
            icon = QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # 存入缓存
            self.avatar_cache[cache_key] = icon

        item.setIcon(icon)
        item.setTextAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.userListWidget.addItem(item)

    def broadcast_user_list(self):
        user_list = list(self.online_users.keys())
        msg = {"type": "user_list", "users": user_list}
        data = (json.dumps(msg) + "\n").encode('utf-8')
        for handler in self.online_users.values():
            handler.socket.write(data)
        self.load_online_users()

    def open_user_manage(self):
        dialog = UserManageDialog(self.conn, self)
        dialog.exec_()

    def toggle_server(self):
        if self.server_running:
            self.stop_server()
        else:
            port = self.spinBox.value()
            if self.tcp_server.listen(QHostAddress.Any, port):
                self.server_running = True
                self.pushButton_2.setText("停止")
                self.log(f"服务器启动，监听端口 {port}")
            else:
                self.log(f"启动失败：端口 {port} 可能已被占用")

    def stop_server(self):
        self.tcp_server.close()
        for handler in list(self.online_users.values()):
            handler.socket.disconnectFromHost()
        self.online_users.clear()
        self.handlers.clear()
        self.server_running = False
        self.pushButton_2.setText("启动")
        self.log("服务器已停止")
        self.load_online_users()

    def on_new_connection(self):
        client_socket = self.tcp_server.nextPendingConnection()
        handler = ClientHandler(client_socket, self)
        self.handlers.append(handler)


# ---------- 用户管理相关类 ----------
class PasswordDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setEchoMode(QLineEdit.Password)
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.DisplayRole)
        editor.setText(value if value else "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text())

    def displayText(self, value, locale):
        return "●" * len(value) if value else ""


class EncodingRuleDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(ENCODING_RULES)
        return combo

    def setEditorData(self, editor, index):
        text = index.data(Qt.DisplayRole)
        if text:
            idx = editor.findText(text)
            if idx >= 0:
                editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())


class AvatarDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dialog = parent

    def createEditor(self, parent, option, index):
        return None

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonDblClick and event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self.dialog, "选择新头像", BASE_DIR, "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if file_path:
                user_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
                cursor = self.dialog.conn.cursor()
                cursor.execute("UPDATE users SET avatar=? WHERE id=?", (file_path, user_id))
                self.dialog.conn.commit()
                self.dialog.load_data()
            return True
        return super().editorEvent(event, model, option, index)


class UserManageDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn 
        uic.loadUi('user_manage.ui', self)

        table = self.tableWidget
        btn_add = self.pushButton
        btn_del = self.pushButton_2
        btn_exit = self.pushButton_3

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(table, 1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)
        right_layout.setAlignment(Qt.AlignTop)

        right_layout.addWidget(btn_add)
        right_layout.addWidget(btn_del)
        right_layout.addWidget(btn_exit)
        right_layout.addStretch()

        main_layout.addLayout(right_layout)

        self.setMinimumSize(500, 400)  

        self.tableWidget.setColumnCount(7)
        self.tableWidget.setHorizontalHeaderLabels(
            ["用户ID", "用户名", "头像", "密码", "编码规则", "锁定", "创建时间"]
        )
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableWidget.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tableWidget.setIconSize(QSize(40, 40))

        self.tableWidget.setItemDelegateForColumn(3, PasswordDelegate(self))
        self.tableWidget.setItemDelegateForColumn(4, EncodingRuleDelegate(self))
        self.tableWidget.setItemDelegateForColumn(2, AvatarDelegate(self))

        self.pushButton.clicked.connect(self.add_user)
        self.pushButton_2.clicked.connect(self.delete_user)
        self.pushButton_3.clicked.connect(self.close)
        self.tableWidget.cellChanged.connect(self.on_cell_changed)

        self.load_data()
        
    def load_data(self):
        self.tableWidget.setRowCount(0)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, avatar, password, encoding_rule, locked, create_time "
            "FROM users ORDER BY id"
        )
        rows = cursor.fetchall()

        for row_data in rows:
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)
            self.tableWidget.setRowHeight(row, 50)

            for col, value in enumerate(row_data):
                if col == 2:
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    real_path = resolve_avatar_path(value, BASE_DIR)
                    if real_path:
                        pixmap = QPixmap(real_path)
                        if not pixmap.isNull():
                            icon = QIcon(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            item.setIcon(icon)
                    item.setToolTip(str(value))
                    item.setText("")
                    self.tableWidget.setItem(row, col, item)
                elif col == 5:
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    item.setCheckState(Qt.Checked if value == 1 else Qt.Unchecked)
                    self.tableWidget.setItem(row, col, item)
                else:
                    item = QTableWidgetItem(str(value))
                    if col == 0 or col == 6:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.tableWidget.setItem(row, col, item)

    def add_user(self):
        dialog = AddUserDialog(self.conn, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_user(self):
        current_row = self.tableWidget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的用户")
            return
        user_id_item = self.tableWidget.item(current_row, 0)
        user_id = int(user_id_item.text())
        reply = QMessageBox.question(self, "确认", "确定删除该用户？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            self.conn.commit()
            self.load_data()

    def on_cell_changed(self, row, col):
        if self.tableWidget.rowCount() == 0:
            return
        user_id_item = self.tableWidget.item(row, 0)
        user_id = int(user_id_item.text())
        if col == 5:   # 锁定列
            item = self.tableWidget.item(row, col)
            locked = 1 if item.checkState() == Qt.Checked else 0
            cursor = self.conn.cursor()
            cursor.execute("UPDATE users SET locked=? WHERE id=?", (locked, user_id))
            # 如果解锁，同时重置失败次数
            if locked == 0:
                cursor.execute("UPDATE users SET login_failures=0 WHERE id=?", (user_id,))
            self.conn.commit()
        elif col in (1, 3, 4):
            item = self.tableWidget.item(row, col)
            new_value = item.text()
            col_names = ['id', 'username', 'avatar', 'password', 'encoding_rule', 'locked', 'create_time']
            cursor = self.conn.cursor()
            cursor.execute(f"UPDATE users SET {col_names[col]}=? WHERE id=?", (new_value, user_id))
            self.conn.commit()


class AddUserDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("添加用户")
        layout = QFormLayout(self)

        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        avatar_layout = QHBoxLayout()
        self.avatar_edit = QLineEdit()
        self.avatar_edit.setPlaceholderText("点击浏览选择图片")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_avatar)
        avatar_layout.addWidget(self.avatar_edit)
        avatar_layout.addWidget(browse_btn)

        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(ENCODING_RULES)
        self.locked_check = QCheckBox("锁定")

        layout.addRow("用户名:", self.username_edit)
        layout.addRow("密码:", self.password_edit)
        layout.addRow("头像路径:", avatar_layout)
        layout.addRow("编码规则:", self.encoding_combo)
        layout.addRow(self.locked_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def browse_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择头像图片", BASE_DIR,
                                                   "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            self.avatar_edit.setText(file_path)

    def accept(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "警告", "用户名和密码不能为空")
            return
        avatar = self.avatar_edit.text().strip() or ""
        encoding_rule = self.encoding_combo.currentText()
        locked = 1 if self.locked_check.isChecked() else 0
        create_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, avatar, password, encoding_rule, locked, login_failures, create_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, avatar, password, encoding_rule, locked, 0, create_time))
            self.conn.commit()
            super().accept()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "错误", "用户名已存在")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
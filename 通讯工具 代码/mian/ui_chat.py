import os
import sqlite3
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem, QLineEdit,
                             QSplitter, QFrame, QMessageBox, QSizePolicy, QFileDialog)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QDateTime
from PyQt5.QtGui import QPixmap, QFont, QFontMetrics
from ui_common import STYLE_SHEET, set_round_avatar, create_default_avatar_icon, resolve_avatar_path, create_round_pixmap
from ui_friend_item import FriendItemWidget
from ui_add_friend import AddFriendDialog

# ---------- 居中时间提醒组件 ----------
class TimeReminderWidget(QWidget):
    """居中时间提醒组件，智能显示时间"""
    def __init__(self, dt, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        time_str = self._format_time(dt)
        time_label = QLabel(time_str)
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet("color: #bbb; background-color: transparent;")
        time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(time_label)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedHeight(40)

    def _format_time(self, dt):
        now = QDateTime.currentDateTime()
        if isinstance(dt, str):
            formats = ["yyyy-MM-dd hh:mm:ss", "hh:mm", "MM-dd", "yyyy-MM-dd"]
            for fmt in formats:
                parsed_dt = QDateTime.fromString(dt, fmt)
                if parsed_dt.isValid():
                    dt = parsed_dt
                    break
            else:
                return dt
        
        if dt.date() == now.date():
            return dt.toString("HH:mm")
        elif dt.date().daysTo(now.date()) == 1:
            return "昨天"
        elif dt.date().year() == now.date().year():
            return dt.toString("MM-dd")
        else:
            return dt.toString("yyyy-MM-dd")

# ---------- 普通消息项 ----------
class MessageItem(QWidget):
    def __init__(self, text, timestamp, is_self=False, sender_name=None, sender_avatar=None, parent=None):
        super().__init__(parent)
        self.is_self = is_self
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.load_avatar(sender_avatar, sender_name)
        self.name_label = QLabel(sender_name if sender_name else "")
        self.name_label.setFont(QFont("Microsoft YaHei", 9))
        self.name_label.setStyleSheet("color: #999;")
        name_height = self.name_label.fontMetrics().height() if not is_self else 0
        bubble_container = QWidget()
        bubble_layout = QVBoxLayout(bubble_container)
        bubble_layout.setSpacing(2)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        if is_self:
            bubble_layout.setAlignment(Qt.AlignRight)
            self.name_label.setAlignment(Qt.AlignRight)
        else:
            bubble_layout.setAlignment(Qt.AlignLeft)
            self.name_label.setAlignment(Qt.AlignLeft)
        self.msg_label = QLabel(text)
        self.msg_label.setWordWrap(True)
        self.msg_label.setMaximumWidth(400)
        font = QFont("Microsoft YaHei", 10)
        self.msg_label.setFont(font)
        metrics = QFontMetrics(font)
        available_width = 400 - 24
        rect = metrics.boundingRect(0, 0, available_width, 0, Qt.TextWordWrap, text)
        text_height = rect.height()
        bubble_content_height = text_height + 16
        if is_self:
            self.msg_label.setStyleSheet("""
                QLabel {
                    background-color: #95EC69;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: black;
                }
            """)
        else:
            self.msg_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: black;
                    border: 1px solid #e0e0e0;
                }
            """)
        if not is_self:
            bubble_layout.addWidget(self.name_label)
        bubble_layout.addWidget(self.msg_label)
        if is_self:
            bubble_container_height = bubble_content_height
        else:
            bubble_container_height = name_height + 2 + bubble_content_height
        total_height = max(40, bubble_container_height) + 10
        self.setFixedHeight(total_height)
        if is_self:
            layout.addStretch()
            layout.addWidget(bubble_container)
            layout.addWidget(self.avatar_label)
        else:
            layout.addWidget(self.avatar_label)
            layout.addWidget(bubble_container)
            layout.addStretch()
        self.setStyleSheet("background-color: transparent;")

    def sizeHint(self):
        return QSize(400, self.height())

    def load_avatar(self, avatar_path, sender_name):
        real_path = resolve_avatar_path(avatar_path)
        if real_path and os.path.exists(real_path):
            pixmap = QPixmap(real_path)
            if not pixmap.isNull():
                round_pixmap = create_round_pixmap(pixmap, 40)
                self.avatar_label.setPixmap(round_pixmap)
                return
        icon = create_default_avatar_icon(40)
        self.avatar_label.setPixmap(icon.pixmap(40, 40))

# ---------- 文件消息项 ----------
class FileMessageItem(QWidget):
    download_request = pyqtSignal(str, str)  # file_id, filename
    def __init__(self, file_id, filename, size, is_self=False, sender_name=None, sender_avatar=None, parent=None):
        super().__init__(parent)
        self.file_id = file_id
        self.filename = filename
        self.size = size  
        self.is_self = is_self
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 头像
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        if sender_avatar:
            real_path = resolve_avatar_path(sender_avatar)
            if real_path and os.path.exists(real_path):
                pixmap = QPixmap(real_path)
                if not pixmap.isNull():
                    round_pixmap = create_round_pixmap(pixmap, 40)
                    self.avatar_label.setPixmap(round_pixmap)
        if self.avatar_label.pixmap() is None:
            icon = create_default_avatar_icon(40)
            self.avatar_label.setPixmap(icon.pixmap(40, 40))
        
        # 名称标签
        self.name_label = QLabel(sender_name if sender_name else "")
        self.name_label.setFont(QFont("Microsoft YaHei", 9))
        self.name_label.setStyleSheet("color: #999;")

        # 气泡容器
        bubble_container = QWidget()
        bubble_container.setMaximumWidth(400)  # 限制整个气泡容器的宽度
        bubble_layout = QVBoxLayout(bubble_container)
        bubble_layout.setSpacing(4)
        bubble_layout.setContentsMargins(0, 0, 0, 0)

        # 文件卡片
        file_widget = QWidget()
        file_widget.setCursor(Qt.PointingHandCursor)
        file_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 6px;
            }
            QWidget:hover {
                background-color: #f5f5f5;
            }
        """)
        file_layout = QHBoxLayout(file_widget)
        file_layout.setContentsMargins(8, 6, 8, 6)
        file_layout.setSpacing(8)

        # 文件图标
        icon_label = QLabel("📄")
        icon_label.setFont(QFont("Segoe UI Emoji", 10))
        file_layout.addWidget(icon_label)

        name_label = QLabel(filename)
        name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        name_label.setMaximumWidth(250)  # 限制文件名宽度
        name_label.setToolTip(filename)  # 鼠标悬停显示完整文件名
        file_layout.addWidget(name_label)

        file_layout.addStretch()

        # 下载按钮
        self.download_btn = QPushButton("↓ 下载")
        self.download_btn.setFixedSize(60, 28)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #07c160;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #06ad56;
            }
        """)
        self.download_btn.clicked.connect(lambda: self.download_request.emit(self.file_id, self.filename))
        file_layout.addWidget(self.download_btn)

        bubble_layout.addWidget(file_widget)


        # 左右布局
        if is_self:
            bubble_layout.setAlignment(Qt.AlignRight)
            self.name_label.setAlignment(Qt.AlignRight)
            layout.addStretch()
            layout.addWidget(bubble_container)
            layout.addWidget(self.avatar_label)
        else:
            bubble_layout.setAlignment(Qt.AlignLeft)
            self.name_label.setAlignment(Qt.AlignLeft)
            layout.addWidget(self.avatar_label)
            layout.addWidget(bubble_container)
            layout.addStretch()

        self.setStyleSheet("background-color: transparent;")
        self.setFixedHeight(70)  # 高度微调更美观

    def sizeHint(self):
        return QSize(400, self.height())

class ChatWindow(QMainWindow):
    send_message_signal = pyqtSignal(str, str)
    logout_signal = pyqtSignal()
    add_friend_signal = pyqtSignal(str)
    search_users_signal = pyqtSignal(str)
    send_file_signal = pyqtSignal(str, str, str)   # to_user, file_path, file_id
    download_file_signal = pyqtSignal(str, str)    # file_id, filename

    def __init__(self, username, avatar_path):
        super().__init__()
        self.username = username
        self.avatar_path = avatar_path
        self.friends_avatars = {}
        self.setWindowTitle(f"信微聊天 - {username}")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)
        self.setStyleSheet(STYLE_SHEET)
        self.current_friend = None
        self.last_messages = {}
        self.friends_info = {}
        self.last_msg_timestamps = {}
        self.unread_counts = {}
        self.local_db_path = os.path.join(os.path.dirname(__file__), f"chat_{username}.db")
        self.init_local_db()
        self.init_ui()

    def init_local_db(self):
        self.local_conn = sqlite3.connect(self.local_db_path)
        cursor = self.local_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                friend TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        # 新增文件消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                friend TEXT NOT NULL,
                sender TEXT NOT NULL,
                file_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                is_self INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        self.local_conn.commit()

    def _save_file_message_to_db(self, friend, sender, file_id, filename, size, is_self, timestamp):
        cursor = self.local_conn.cursor()
        cursor.execute('''
            INSERT INTO file_messages (friend, sender, file_id, filename, size, is_self, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (friend, sender, file_id, filename, size, 1 if is_self else 0, timestamp))
        self.local_conn.commit()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部栏
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("#topBar { background-color: #2b2b2b; border-bottom: 1px solid #333; }")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        top_layout.setSpacing(15)

        self.user_avatar_label = QLabel()
        self.user_avatar_label.setFixedSize(44, 44)
        self.user_avatar_label.setStyleSheet("background-color: transparent;")
        self.update_user_avatar()

        self.user_name_label = QLabel(self.username)
        self.user_name_label.setStyleSheet("color: white; font-size: 16px; font-weight: 500; background-color: transparent;")
        self.user_name_label.setMinimumWidth(100)

        top_layout.addWidget(self.user_avatar_label)
        top_layout.addWidget(self.user_name_label)
        top_layout.addStretch()

        add_friend_btn = QPushButton("＋ 添加好友")
        add_friend_btn.setFixedSize(120, 36)
        add_friend_btn.setCursor(Qt.PointingHandCursor)
        add_friend_btn.setStyleSheet("""
            QPushButton {
                background-color: #07c160;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #06ad56; }
        """)
        add_friend_btn.clicked.connect(self.on_add_friend_clicked)
        top_layout.addWidget(add_friend_btn)

        logout_btn = QPushButton("注销")
        logout_btn.setFixedSize(80, 36)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: 1px solid #555;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #333; }
        """)
        logout_btn.clicked.connect(self.on_logout_clicked)
        top_layout.addWidget(logout_btn)

        main_layout.addWidget(top_bar)

        # 主体分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e0e0e0; }")

        # 左侧联系人列表
        self.contact_list = QListWidget()
        self.contact_list.setMaximumWidth(320)
        self.contact_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: none;
                outline: none;
            }
        """)
        self.contact_list.setSpacing(0)
        splitter.addWidget(self.contact_list)

        # 右侧聊天区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.chat_title = QLabel("选择一个好友开始聊天")
        self.chat_title.setFixedHeight(56)
        self.chat_title.setAlignment(Qt.AlignCenter)
        self.chat_title.setStyleSheet("background-color: white; border-bottom: 1px solid #e0e0e0; font-weight: bold; font-size: 16px;")
        right_layout.addWidget(self.chat_title)

        # 消息列表
        self.message_list = QListWidget()
        self.message_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
            }
            QListWidget::item {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }
        """)
        self.message_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.message_list.setSelectionMode(QListWidget.NoSelection)
        self.message_list.setSpacing(2)
        right_layout.addWidget(self.message_list, 1)

        # 输入区域（包含文件按钮）
        input_widget = QWidget()
        input_widget.setFixedHeight(80)
        input_widget.setStyleSheet("background-color: white; border-top: 1px solid #e9ecef;")
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(20, 12, 20, 12)
        input_layout.setSpacing(15)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("输入消息...")
        self.message_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
                background-color: white;
            }
        """)
        self.message_edit.returnPressed.connect(self.on_send_clicked)
        input_layout.addWidget(self.message_edit)

        self.file_btn = QPushButton("📎 文件")
        self.file_btn.setFixedSize(85, 40)
        self.file_btn.setCursor(Qt.PointingHandCursor)
        self.file_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        try:
            self.file_btn.clicked.disconnect(self.on_send_file_clicked)
        except TypeError:
                pass
        self.file_btn.clicked.connect(self.on_send_file_clicked)

        input_layout.addWidget(self.file_btn)
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(85, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #07c160;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #06ad56;
            }
        """)
        try:
            self.send_btn.clicked.disconnect(self.on_send_clicked)
        except TypeError:
            pass
        self.send_btn.clicked.connect(self.on_send_clicked)
        input_layout.addWidget(self.send_btn)
        right_layout.addWidget(input_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([320, 780])

        main_layout.addWidget(splitter)

    def update_user_avatar(self):
        set_round_avatar(self.user_avatar_label, self.avatar_path, 44)

    def on_send_clicked(self):
        if not self.current_friend:
            QMessageBox.warning(self, "提示", "请先选择一个好友")
            return
        content = self.message_edit.text().strip()
        if not content:
            return
        current_time = QDateTime.currentDateTime()
        time_str = current_time.toString("yyyy-MM-dd hh:mm:ss")
        cursor = self.local_conn.cursor()
        cursor.execute('''
            INSERT INTO messages (friend, sender, content, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (self.current_friend, self.username, content, time_str))
        self.local_conn.commit()
        self.send_message_signal.emit(self.current_friend, content)
        self.message_edit.clear()
        self.append_message(self.username, content, is_self=True, timestamp=time_str)
        self.last_messages[self.current_friend] = (content, current_time.toString("hh:mm"))
        self.update_friend_list(list(self.friends_info.values()))

    def on_logout_clicked(self):
        self.logout_signal.emit()
        self.close()

    def on_add_friend_clicked(self):
        dialog = AddFriendDialog(self)
        dialog.search_signal.connect(self.on_search_users)
        dialog.add_friend_signal.connect(self.on_add_friend_confirm)
        dialog.exec_()

    def on_search_users(self, keyword):
        self.search_users_signal.emit(keyword)

    def on_add_friend_confirm(self, username):
        self.add_friend_signal.emit(username)

    def on_send_file_clicked(self):
        if not self.current_friend:
            QMessageBox.warning(self, "提示", "请先选择一个好友")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            import uuid
            file_id = str(uuid.uuid4())
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            self.append_file_message(file_id, filename, size, is_self=True)
            self.send_file_signal.emit(self.current_friend, file_path, file_id)

    def append_file_message(self, file_id, filename, size, is_self=False, sender_name=None, sender_avatar=None):
        # 确定消息的发送者和好友标识
        sender = sender_name if sender_name else self.username
        friend = sender if not is_self else self.current_friend
        if not friend:
            return

        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        
        # 如果不是当前聊天对象，只存储，不显示
        if not is_self and sender != self.current_friend:
            self._save_file_message_to_db(friend, sender, file_id, filename, size, is_self, current_time)
            # 增加未读计数
            self.unread_counts[friend] = self.unread_counts.get(friend, 0) + 1
            self.update_friend_unread(friend, self.unread_counts[friend])
            return

        # 以下为当前聊天对象的显示逻辑
        current_dt = QDateTime.currentDateTime()
        show_time = current_dt.toString("hh:mm")
        last_dt = self.last_msg_timestamps.get(self.current_friend)
        if last_dt is None or last_dt.secsTo(current_dt) >= 180:
            self._add_time_reminder(current_dt)
        self.last_msg_timestamps[self.current_friend] = current_dt

        avatar_path = self.avatar_path if is_self else self.friends_avatars.get(sender_name, "")
        item = QListWidgetItem(self.message_list)
        widget = FileMessageItem(file_id, filename, size, is_self, sender_name, avatar_path)
        widget.download_request.connect(self.on_file_download_request)
        item.setSizeHint(widget.sizeHint())
        self.message_list.setItemWidget(item, widget)
        self.message_list.scrollToBottom()

        # 存储到数据库
        self._save_file_message_to_db(friend, sender, file_id, filename, size, is_self, current_time)

    def on_file_download_request(self, file_id, filename):
        self.download_file_signal.emit(file_id, filename)

    def _clear_all_selected(self):
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and hasattr(widget, 'set_selected'):
                widget.set_selected(False)

    def _on_friend_widget_clicked(self, username):
        if self.current_friend == username:
            return
        self.current_friend = username
        self.chat_title.setText(f"与 {self.current_friend} 聊天中")
        if self.current_friend in self.unread_counts:
            self.unread_counts[self.current_friend] = 0
            self.update_friend_unread(self.current_friend, 0)
        self._clear_all_selected()
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            if item.data(Qt.UserRole) == username:
                widget = self.contact_list.itemWidget(item)
                if widget:
                    widget.set_selected(True)
                break
        self.load_chat_history(self.current_friend)

    def load_chat_history(self, friend):
        self.message_list.clear()
        self.last_msg_timestamps[friend] = None

        cursor = self.local_conn.cursor()
        # 获取文本消息
        cursor.execute('SELECT sender, content, timestamp FROM messages WHERE friend = ?', (friend,))
        text_msgs = [('text', row[0], row[1], row[2]) for row in cursor.fetchall()]
        # 获取文件消息
        cursor.execute('SELECT sender, file_id, filename, size, is_self, timestamp FROM file_messages WHERE friend = ?', (friend,))
        file_msgs = [('file', row[0], row[1], row[2], row[3], row[4], row[5]) for row in cursor.fetchall()]

        all_msgs = text_msgs + file_msgs
        all_msgs.sort(key=lambda x: x[-1])  # 按时间戳排序

        # 插入时间提醒
        last_dt = None
        for msg in all_msgs:
            timestamp = msg[-1]
            dt = QDateTime.fromString(timestamp, "yyyy-MM-dd hh:mm:ss")
            if not dt.isValid():
                dt = QDateTime.currentDateTime()
            if last_dt is None or last_dt.secsTo(dt) >= 180:
                self._add_time_reminder(dt)
            last_dt = dt

            # 显示消息
            if msg[0] == 'text':
                _, sender, content, _ = msg
                is_self = (sender == self.username)
                self._append_text_message(sender, content, is_self, timestamp)
            else:
                _, sender, file_id, filename, size, is_self, _ = msg
                self._display_file_message(sender, file_id, filename, size, is_self, timestamp)

        self.message_list.scrollToBottom()

    def update_friend_unread(self, username, count):
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            if item.data(Qt.UserRole) == username:
                widget = self.contact_list.itemWidget(item)
                if widget and hasattr(widget, 'set_unread'):
                    widget.set_unread(count)
                break

    def update_friend_list(self, friends):
        self.contact_list.clear()
        self.friends_info = {}
        for f in friends:
            username = f['username']
            avatar_path = f['avatar']
            self.friends_info[username] = f
            self.friends_avatars[username] = avatar_path
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 75))
            last_msg, last_time = self.last_messages.get(username, ("", ""))
            unread_count = self.unread_counts.get(username, 0)
            widget = FriendItemWidget(username, avatar_path, last_msg, last_time, unread_count)
            widget.item_clicked.connect(self._on_friend_widget_clicked)
            self.contact_list.addItem(item)
            self.contact_list.setItemWidget(item, widget)
            item.setData(Qt.UserRole, username)
        if self.current_friend and self.current_friend in self.friends_info:
            for i in range(self.contact_list.count()):
                item = self.contact_list.item(i)
                if item.data(Qt.UserRole) == self.current_friend:
                    widget = self.contact_list.itemWidget(item)
                    if widget:
                        widget.set_selected(True)
                    break
        else:
            self.current_friend = None
            self.chat_title.setText("选择一个好友开始聊天")
            self.message_list.clear()

    def receive_message(self, from_user, content, timestamp):
        cursor = self.local_conn.cursor()
        cursor.execute('''
            INSERT INTO messages (friend, sender, content, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (from_user, from_user, content, timestamp))
        self.local_conn.commit()
        if from_user == self.current_friend:
            self.append_message(from_user, content, is_self=False, timestamp=timestamp)
        else:
            self.unread_counts[from_user] = self.unread_counts.get(from_user, 0) + 1
            self.update_friend_unread(from_user, self.unread_counts[from_user])
        self.last_messages[from_user] = (content, timestamp.split(' ')[1][:5] if ' ' in timestamp else timestamp)
        if hasattr(self, 'friends_info'):
            friends = list(self.friends_info.values())
            self.update_friend_list(friends)

    def append_message(self, sender, msg, is_self=False, timestamp=None):
        friend = self.current_friend
        if not friend:
            return
        if timestamp is None:
            current_dt = QDateTime.currentDateTime()
            timestamp = current_dt.toString("yyyy-MM-dd hh:mm:ss")
        else:
            current_dt = QDateTime.fromString(timestamp, "yyyy-MM-dd hh:mm:ss")
        
        last_dt = self.last_msg_timestamps.get(friend)
        if last_dt is None or last_dt.secsTo(current_dt) >= 180:
            self._add_time_reminder(current_dt)
        self.last_msg_timestamps[friend] = current_dt
        
        self._append_text_message(sender, msg, is_self, timestamp)
        self.message_list.scrollToBottom()

    def _add_time_reminder(self, dt):
        time_item = QListWidgetItem(self.message_list)
        time_widget = TimeReminderWidget(dt)
        time_item.setSizeHint(time_widget.sizeHint())
        self.message_list.setItemWidget(time_item, time_widget)


    def _append_text_message(self, sender, msg, is_self, timestamp):
        friend = self.current_friend
        if not friend:
            return
        dt = QDateTime.fromString(timestamp, "yyyy-MM-dd hh:mm:ss")
        show_time = dt.toString("hh:mm")
        if is_self:
            avatar_path = self.avatar_path
            sender_name = None
        else:
            avatar_path = self.friends_avatars.get(sender, "")
            sender_name = sender
        item = QListWidgetItem(self.message_list)
        widget = MessageItem(msg, show_time, is_self, sender_name, avatar_path)
        item.setSizeHint(widget.sizeHint())
        self.message_list.setItemWidget(item, widget)

    def _display_file_message(self, sender, file_id, filename, size, is_self, timestamp):
        friend = self.current_friend
        if not friend:
            return
        dt = QDateTime.fromString(timestamp, "yyyy-MM-dd hh:mm:ss")
        show_time = dt.toString("hh:mm")
        if is_self:
            avatar_path = self.avatar_path
            sender_name = None
        else:
            avatar_path = self.friends_avatars.get(sender, "")
            sender_name = sender
        item = QListWidgetItem(self.message_list)
        widget = FileMessageItem(file_id, filename, size, is_self, sender_name, avatar_path)
        widget.download_request.connect(self.on_file_download_request)
        item.setSizeHint(widget.sizeHint())
        self.message_list.setItemWidget(item, widget)
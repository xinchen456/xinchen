import os
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QSize, QDateTime, pyqtSignal
# 【关键修复】确保导入 QFontMetrics
from PyQt5.QtGui import QPixmap, QFont, QFontMetrics

from ui_common import resolve_avatar_path, create_round_pixmap, create_default_avatar_icon


class FriendItemWidget(QWidget):
    """好友列表项（基于回退版修复）"""
    # 点击信号：传递用户名，父容器处理互斥
    item_clicked = pyqtSignal(str)

    def __init__(self, username, avatar_path, last_msg="", last_time="", unread_count=0, parent=None):
        super().__init__(parent)
        self.username = username
        self.avatar_path = avatar_path
        self.last_msg = last_msg
        self.last_time = last_time
        self.unread_count = unread_count

        self.is_selected = False
        self.is_hovered = False

        self.UI_CONFIG = {
            "item_height": 70,
            "avatar_size": 50,
            "margins": (12, 8, 12, 8),
            "spacing": 12,
            "font_name": "Microsoft YaHei",
            "normal_bg": "transparent",
            "hover_bg": "#f5f7fa",
            "selected_bg": "#e8f5e9",
            "name_color": "#1f2329",
            "msg_color": "#86909c",
            "time_color": "#c9cdd4",
            "unread_bg": "#ff4d4f",
        }

        # 【保留回退版逻辑】直接初始化
        self.init_ui()

    def init_ui(self):
        # 【保留回退版逻辑】主布局
        self.setFixedHeight(self.UI_CONFIG["item_height"])
        self.setMinimumWidth(260)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(*self.UI_CONFIG["margins"])
        content_layout.setSpacing(self.UI_CONFIG["spacing"])
        content_layout.setAlignment(Qt.AlignVCenter)

        # 头像
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(self.UI_CONFIG["avatar_size"], self.UI_CONFIG["avatar_size"])
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("background-color: transparent; border: none;")
        self._load_avatar()
        content_layout.addWidget(self.avatar_label)

        # 信息区域
        info_widget = QWidget()
        info_widget.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Preferred)
        info_widget.setStyleSheet("background-color: transparent; border: none;")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignVCenter)

        # 顶部行
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        # 昵称
        self.name_label = QLabel(self.username)
        self.name_label.setFont(QFont(self.UI_CONFIG["font_name"], 14, QFont.Medium))
        self.name_label.setStyleSheet(f"color: {self.UI_CONFIG['name_color']}; background-color: transparent;")
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_font_metrics = QFontMetrics(self.name_label.font())
        elided_name = name_font_metrics.elidedText(self.username, Qt.ElideRight, 120)
        self.name_label.setText(elided_name)
        self.name_label.setToolTip(self.username)

        # 未读
        self.unread_label = QLabel()
        self.unread_label.setFont(QFont(self.UI_CONFIG["font_name"], 10, QFont.Bold))
        self.unread_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.UI_CONFIG['unread_bg']};
                color: white;
                border-radius: 9px;
                padding: 0px 5px;
                min-width: 18px;
                max-width: 36px;
                height: 18px;
                font-size: 10px;
                border: none;
            }}
        """)
        self.unread_label.setAlignment(Qt.AlignCenter)
        self._update_unread_text()

        # 时间
        self.time_label = QLabel(self._format_time(self.last_time))
        self.time_label.setFont(QFont(self.UI_CONFIG["font_name"], 10))
        self.time_label.setStyleSheet(f"color: {self.UI_CONFIG['time_color']}; background-color: transparent;")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setFixedWidth(50)

        top_layout.addWidget(self.name_label)
        top_layout.addWidget(self.unread_label)
        top_layout.addStretch()
        top_layout.addWidget(self.time_label)

        # 最后消息
        self.msg_label = QLabel()
        self.msg_label.setFont(QFont(self.UI_CONFIG["font_name"], 11))
        self.msg_label.setStyleSheet(f"color: {self.UI_CONFIG['msg_color']}; background-color: transparent;")
        self.msg_label.setWordWrap(False)
        self.msg_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.msg_label.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Preferred)
        self._update_msg_text(self.last_msg)

        info_layout.addLayout(top_layout)
        info_layout.addWidget(self.msg_label)
        content_layout.addWidget(info_widget, 1)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        
        self.update_style()

    def _load_avatar(self):
        try:
            real_path = resolve_avatar_path(self.avatar_path)
            if real_path and os.path.exists(real_path):
                pixmap = QPixmap(real_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        self.UI_CONFIG["avatar_size"], self.UI_CONFIG["avatar_size"],
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    round_pixmap = create_round_pixmap(pixmap, self.UI_CONFIG["avatar_size"])
                    self.avatar_label.setPixmap(round_pixmap)
                    return
        except Exception:
            pass
        icon = create_default_avatar_icon(self.UI_CONFIG["avatar_size"])
        self.avatar_label.setPixmap(icon.pixmap(self.UI_CONFIG["avatar_size"], self.UI_CONFIG["avatar_size"]))

    def _update_unread_text(self):
        if self.unread_count > 0:
            display_text = str(self.unread_count) if self.unread_count <= 99 else "99+"
            self.unread_label.setText(display_text)
            font_metrics = QFontMetrics(self.unread_label.font())
            text_width = font_metrics.boundingRect(display_text).width()
            self.unread_label.setFixedWidth(max(18, text_width + 10))
            self.unread_label.setVisible(True)
        else:
            self.unread_label.setVisible(False)
            self.unread_label.setText("")

    def set_unread(self, count):
        self.unread_count = max(0, int(count))
        self._update_unread_text()

    def _format_time(self, time_str):
        if not time_str:
            return ""
        try:
            if ' ' in time_str:
                dt = QDateTime.fromString(time_str, "yyyy-MM-dd hh:mm")
                if not dt.isValid():
                    dt = QDateTime.fromString(time_str, "yyyy-MM-dd HH:mm:ss")
            else:
                dt = QDateTime.fromString(time_str, "yyyy-MM-dd")
            
            if dt.isValid():
                now = QDateTime.currentDateTime()
                if dt.date() == now.date():
                    return dt.toString("HH:mm")
                elif dt.date().daysTo(now.date()) == 1:
                    return "昨天"
                elif dt.date().year() == now.date().year():
                    return dt.toString("MM-dd")
                else:
                    return dt.toString("yyyy-MM")
            return time_str
        except Exception:
            return time_str

    def _update_msg_text(self, msg):
        msg = msg or ""
        font_metrics = QFontMetrics(self.msg_label.font())
        elided_msg = font_metrics.elidedText(msg, Qt.ElideRight, 220)
        self.msg_label.setText(elided_msg)
        self.msg_label.setToolTip(msg)

    def update_last_message(self, msg, time_str):
        self.last_msg = msg
        self.last_time = time_str
        self._update_msg_text(msg)
        self.time_label.setText(self._format_time(time_str))

    def update_style(self):
        if self.is_selected:
            bg_color = self.UI_CONFIG["selected_bg"]
        elif self.is_hovered:
            bg_color = self.UI_CONFIG["hover_bg"]
        else:
            bg_color = self.UI_CONFIG["normal_bg"]
        
        self.setStyleSheet(f"""
            FriendItemWidget {{
                background-color: {bg_color};
                border: none;
            }}
        """)

    def set_selected(self, selected):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update_style()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.item_clicked.emit(self.username)
        super().mousePressEvent(event)

    def sizeHint(self):
        return QSize(300, self.UI_CONFIG["item_height"])
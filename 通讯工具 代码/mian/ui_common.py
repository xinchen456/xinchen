import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import QLabel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 全局样式表（基于回退版优化：去阴影、去无效属性）
STYLE_SHEET = """
/* 全局基础样式 */
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 10pt;
    background-color: #f8f9fa;
}

/* 输入框、选择框通用样式 */
QLineEdit, QTextEdit, QComboBox {
    border: 1px solid #e2e4e8;
    border-radius: 8px;
    padding: 10px 12px;
    background-color: white;
    selection-background-color: #007AFF;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #07c160;
    outline: none;
}

/* 按钮样式 */
QPushButton {
    background-color: #07c160;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #06b055;
}
QPushButton:pressed {
    background-color: #059c4b;
}
QPushButton:disabled {
    background-color: #b0d4ff;
}

/* 左侧联系人列表：去阴影，背景统一 */
QListWidget {
    border: none;
    background-color: #f8f9fa; /* 与全局一致，去色块阴影 */
    outline: none;
    padding: 0;
}
QListWidget::item {
    border: none;
    background-color: transparent;
    padding: 0;
    margin: 0;
}
QListWidget::item:selected {
    background-color: #e8f5e9;
}
QListWidget::item:hover:!selected {
    background-color: #f5f7fa;
}

/* 右侧聊天区域背景 */
#chat_display {
    background-color: #eef2f5;
    border: none;
    padding: 12px;
}

/* 顶部栏 */
.top-bar {
    background-color: white;
    border-bottom: 1px solid #e9ecef;
    padding: 8px 16px;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #c0c4cc;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a0a4ac;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    height: 0px;
    background: transparent;
}
"""

def resolve_avatar_path(path):
    """解析头像路径（相对/绝对）"""
    if not path:
        return None
    # 尝试原始路径
    if os.path.isabs(path) and os.path.exists(path):
        return path
    if os.path.exists(path):
        return os.path.abspath(path)
    # 尝试相对于BASE_DIR的路径
    abs_path = os.path.join(BASE_DIR, path)
    if os.path.exists(abs_path):
        return abs_path
    # 尝试大小写不敏感匹配
    if path:
        dir_path = os.path.dirname(abs_path)
        orig_filename = os.path.basename(abs_path)
        orig_name = os.path.splitext(orig_filename)[0]
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                name = os.path.splitext(filename)[0]
                if name.lower() == orig_name.lower():
                    return os.path.join(dir_path, filename)
    # 尝试在常见头像目录中查找
    avatar_dirs = [
        BASE_DIR,
        os.path.join(BASE_DIR, 'avatars'),
        os.path.join(BASE_DIR, 'server_files')
    ]
    if path:
        orig_filename = os.path.basename(path)
        orig_name = os.path.splitext(orig_filename)[0]
        for avatar_dir in avatar_dirs:
            if os.path.exists(avatar_dir):
                for filename in os.listdir(avatar_dir):
                    name = os.path.splitext(filename)[0]
                    if name.lower() == orig_name.lower():
                        return os.path.join(avatar_dir, filename)
    # 尝试不同文件格式
    if path:
        name_without_ext = os.path.splitext(os.path.basename(path))[0]
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            for avatar_dir in avatar_dirs:
                test_path = os.path.join(avatar_dir, name_without_ext + ext)
                if os.path.exists(test_path):
                    return test_path
    return None

def create_round_pixmap(pixmap, size):
    """将QPixmap裁剪为圆形"""
    result = QPixmap(size, size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    painter.drawPixmap((size - scaled.width())//2, (size - scaled.height())//2, scaled)
    painter.end()
    return result

def create_default_avatar_icon(size=40):
    """生成灰色默认圆形头像"""
    from PyQt5.QtGui import QIcon
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(180, 180, 180))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, size-4, size-4)
    painter.end()
    return QIcon(pixmap)

def set_round_avatar(label, pixmap_or_path, size):
    """设置QLabel为圆形头像"""
    try:
        if isinstance(pixmap_or_path, str):
            path = pixmap_or_path
            real_path = resolve_avatar_path(path)
            if real_path:
                pixmap = QPixmap(real_path)
            else:
                label.setPixmap(create_default_avatar_icon(size).pixmap(size, size))
                return
        else:
            pixmap = pixmap_or_path
        if pixmap.isNull():
            label.setPixmap(create_default_avatar_icon(size).pixmap(size, size))
            return
        round_pixmap = create_round_pixmap(pixmap, size)
        label.setPixmap(round_pixmap)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("background-color: transparent; border: none;")
    except Exception as e:
        print(f"设置圆形头像失败：{e}")
        label.setPixmap(create_default_avatar_icon(size).pixmap(size, size))
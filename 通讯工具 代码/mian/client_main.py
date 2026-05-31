import sys
import json
import os
import base64
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QDialog
from PyQt5.QtCore import QDateTime, QTimer
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtWidgets import QDialog

from ui_common import STYLE_SHEET
from ui_login import LoginDialog
from ui_register import RegisterDialog
from ui_chat import ChatWindow

class Client:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyleSheet(STYLE_SHEET)

        self.socket = QTcpSocket(self.app)
        self.socket.readyRead.connect(self.on_ready_read)
        self.socket.disconnected.connect(self.on_disconnected)
        self.socket.error.connect(self.on_error)

        self.login_dialog = None
        self.current_window = None
        self.user_id = None
        self.username = None
        self.avatar_path = None
        self.server_host = None
        self.server_port = None
        self._manual_logout = False
        self._force_logout = False
        self.unread_counts = {}
        self.file_receivers = {}
        self.register_dialog = None   # 保存注册对话框实例
        self._login_failed = False          # 新增标志，用于区分登录失败导致的断开
        self.pending_files = {}   # 待发送文件容器
        self.file_send_lock = {} 

    def run(self):
        self.login_dialog = LoginDialog()
        self.login_dialog.login_attempt.connect(self.handle_login)
        self.login_dialog.register_btn.clicked.connect(self.open_register_dialog)
        if self.login_dialog.exec_() == LoginDialog.Accepted:
            sys.exit(self.app.exec_())
        else:
            sys.exit(0)

    def open_register_dialog(self):
        host, port = self.login_dialog.get_server_address()
        self.register_dialog = RegisterDialog(host, port, self.login_dialog)
        self.register_dialog.register_attempt.connect(self.handle_register)
        self.register_dialog.exec_()
        self.register_dialog = None   # 对话框关闭后清空

    def handle_register(self, host, port, username, password, encoding, avatar):
        temp_socket = QTcpSocket()
        temp_socket.connectToHost(host, port)
        if not temp_socket.waitForConnected(3000):
            if self.register_dialog:
                self.register_dialog.register_failed("无法连接到服务器")
            else:
                QMessageBox.critical(self.login_dialog, "错误", "无法连接到服务器")
            return

        reg_msg = {
            "type": "register",
            "username": username,
            "password": password,
            "encoding": encoding,
            "avatar": avatar
        }
        temp_socket.write((json.dumps(reg_msg) + "\n").encode('utf-8'))
        if not temp_socket.waitForReadyRead(3000):
            if self.register_dialog:
                self.register_dialog.register_failed("服务器无响应")
            return

        response = temp_socket.readAll().data().decode('utf-8').strip()
        temp_socket.close()

        try:
            msg = json.loads(response)
            if msg.get('success'):
                # 注册成功，关闭注册对话框
                if self.register_dialog:
                    self.register_dialog.register_success()
                # 自动填充用户名到登录框
                if self.login_dialog:
                    self.login_dialog.username_edit.setText(username)
            else:
                if self.register_dialog:
                    self.register_dialog.register_failed(msg.get('message', '注册失败'))
                else:
                    QMessageBox.critical(self.login_dialog, "失败", msg.get('message', '注册失败'))
        except Exception as e:
            if self.register_dialog:
                self.register_dialog.register_failed(f"数据解析错误: {e}")
            else:
                QMessageBox.critical(self.login_dialog, "错误", "服务器返回数据格式错误")

    def handle_login(self, host, port, username, password):
        self.server_host = host
        self.server_port = port
        self.username = username
        self.password = password

        self.socket.connectToHost(host, port)
        self.socket.connected.connect(self.send_login)
        self.login_dialog.status_label.setText("正在连接服务器...")
        self.login_dialog.login_btn.setEnabled(False)
        self.login_dialog.register_btn.setEnabled(False)

    def send_login(self):
        login_msg = {
            "type": "login",
            "username": self.username,
            "password": self.password
        }
        self.send_json(login_msg)
        self.socket.connected.disconnect(self.send_login)

    def send_json(self, data):
        json_str = json.dumps(data) + "\n"
        self.socket.write(json_str.encode('utf-8'))

    def on_ready_read(self):
        while self.socket.bytesAvailable() > 0:
            line = self.socket.readLine()
            if not line:
                break
            data = line.data().decode('utf-8').strip()
            if not data:
                continue
            try:
                msg = json.loads(data)
                self.handle_message(msg)
            except Exception as e:
                print(f"[错误] 消息解析失败: {e}, 原始数据: {data}")

    def handle_message(self, msg):
        msg_type = msg.get('type')
        if msg_type == 'login_response':
            self.handle_login_response(msg)
        elif msg_type == 'user_list':
            self.handle_user_list(msg)
        elif msg_type == 'message':
            self.handle_chat_message(msg)
        elif msg_type == 'friend_list':
            self.handle_friend_list(msg)
        elif msg_type == 'search_response':
            self.handle_search_response(msg)
        elif msg_type == 'add_friend_response':
            self.handle_add_friend_response(msg)
        elif msg_type == 'friend_request_notify':
            self.handle_friend_request_notify(msg)
        elif msg_type == 'friend_request_response':
            self.handle_friend_request_response(msg)
        elif msg_type == 'friend_request_rejected':
            self.handle_friend_request_rejected(msg)
        elif msg_type == 'search_users_response':
            self.handle_search_users_response(msg)
        elif msg_type == 'force_logout':
            self.handle_force_logout(msg)
        elif msg_type == 'file_message':
            self.handle_file_message(msg)
        elif msg_type == 'file_chunk':
            self.handle_file_chunk(msg)
        elif msg_type == 'file_complete':
            self.handle_file_complete(msg)
        elif msg_type == 'file_accept':
            pass
        elif msg_type == 'file_reject':
            QMessageBox.warning(self.current_window, "提示", "对方拒绝了文件传输")

    def handle_login_response(self, msg):
        if msg.get('success'):
            self.user_id = msg.get('user_id')
            self.avatar_path = msg.get('avatar', '')
            if self.login_dialog:
                self.login_dialog.login_success()
                self.login_dialog = None

            self.current_window = ChatWindow(self.username, self.avatar_path)
            self.current_window.send_message_signal.connect(self.send_chat_message)
            self.current_window.logout_signal.connect(self.logout)
            self.current_window.add_friend_signal.connect(self.on_add_friend)
            self.current_window.search_users_signal.connect(self.send_search_users)
            self.current_window.send_file_signal.connect(self.send_file)
            self.current_window.download_file_signal.connect(self.download_file)
            self.current_window.show()
        else:
            if self.login_dialog:
                self.login_dialog.login_failed(msg.get('message', '未知错误'))
                self._login_failed = True
                self.socket.disconnectFromHost()   # 主动断开，触发 on_disconnected

    def handle_user_list(self, msg):
        online_users = msg.get('users', [])
        if self.current_window:
            friends = list(self.current_window.friends_info.values())
            for f in friends:
                f['online'] = f['username'] in online_users
            self.current_window.update_friend_list(friends)

    def handle_friend_list(self, msg):
        friends = msg.get('friends', [])
        if self.current_window:
            self.current_window.update_friend_list(friends)

    def handle_chat_message(self, msg):
        from_user = msg.get('from')
        content = msg.get('content')
        timestamp = msg.get('timestamp', QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))
        if self.current_window:
            self.current_window.receive_message(from_user, content, timestamp)

    def handle_search_response(self, msg):
        exists = msg.get('exists')
        username = msg.get('username')
        if exists:
            reply = QMessageBox.question(self.current_window, "确认添加",
                                         f"是否添加 {username} 为好友？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                add_msg = {"type": "add_friend", "username": username}
                self.send_json(add_msg)
        else:
            QMessageBox.information(self.current_window, "提示", f"用户 {username} 不存在")

    def handle_add_friend_response(self, msg):
        if msg.get('success'):
            QMessageBox.information(self.current_window, "成功", "好友添加成功")
        else:
            QMessageBox.warning(self.current_window, "失败", msg.get('message', '未知错误'))

    def send_chat_message(self, to_user, content):
        msg = {
            "type": "message",
            "to": to_user,
            "content": content,
            "timestamp": QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        }
        self.send_json(msg)

    def on_add_friend(self, target):
        request_msg = {"type": "friend_request", "to": target}
        self.send_json(request_msg)

    def logout(self):
        self._manual_logout = True
        logout_msg = {"type": "logout"}
        self.send_json(logout_msg)
        QTimer.singleShot(100, self.socket.disconnectFromHost)
        if self.current_window:
            self.current_window.close()
            self.current_window = None

    def on_disconnected(self):
        if self._force_logout:
            self._force_logout = False
            return
        if self._manual_logout:
            self._manual_logout = False
            return
            
        if self._login_failed:
            self._login_failed = False
            if self.login_dialog and self.login_dialog.isVisible():
                self.login_dialog.login_btn.setEnabled(True)
                self.login_dialog.register_btn.setEnabled(True)
            return
            
        if self.current_window:
            QMessageBox.critical(self.current_window, "连接断开", "与服务器的连接已断开")
            self.current_window.close()
            self.current_window = None
        self.run()

    def on_error(self, socket_error):
        error_msg = self.socket.errorString()
        if self.login_dialog and self.login_dialog.isVisible():
            self.login_dialog.login_failed(f"连接错误: {error_msg}")
        else:
            QMessageBox.critical(None, "网络错误", error_msg)

    def handle_friend_request_notify(self, msg):
        from_user = msg.get('from')
        request_time = msg.get('request_time')
        reply = QMessageBox.question(self.current_window, "好友申请",
                                    f"{from_user} 请求添加你为好友\n时间: {request_time}",
                                    QMessageBox.Yes | QMessageBox.No)
        agree = reply == QMessageBox.Yes
        response_msg = {
            "type": "friend_request_response",
            "from": from_user,
            "agree": agree
        }
        self.send_json(response_msg)

    def handle_friend_request_response(self, msg):
        if msg.get('success'):
            QMessageBox.information(self.current_window, "提示", msg.get('message', '操作成功'))
        else:
            QMessageBox.warning(self.current_window, "失败", msg.get('message', '操作失败'))

    def handle_friend_request_rejected(self, msg):
        from_user = msg.get('from')
        QMessageBox.information(self.current_window, "提示", f"{from_user} 拒绝了你的好友申请")

    def handle_search_users_response(self, msg):
        users = msg.get('users', [])
        if self.current_window:
            for child in self.current_window.findChildren(QDialog):
                if child.__class__.__name__ == 'AddFriendDialog':
                    child.update_results(users)
                    break

    def send_search_users(self, keyword):
        msg = {"type": "search_users", "keyword": keyword}
        self.send_json(msg)
    
    def handle_force_logout(self, msg):
        force_logout_msg = msg.get('message', '您的账号在其他设备登录，您已被强制下线')
        
        self._force_logout = True
        self._manual_logout = True
        
        if self.current_window:
            QMessageBox.warning(self.current_window, "下线通知", force_logout_msg)
        try:
            if self.socket.isValid():
                self.socket.disconnectFromHost()
        except:
            pass
        if self.current_window:
            try:
                self.current_window.close()
                self.current_window = None
            except:
                pass
        QTimer.singleShot(300, self._restart_login)

    def _restart_login(self):
        try:
            # 1. 清理所有标志位
            self._force_logout = False
            self._manual_logout = False
            self._login_failed = False
            for file_id in list(self.file_receivers.keys()):
                try:
                    info = self.file_receivers[file_id]
                    if info.get('file_handle') and not info['file_handle'].closed:
                        info['file_handle'].close()
                except Exception as e:
                    print(f"清理文件句柄出错: {e}")
            self.file_receivers.clear()
            self.pending_files.clear()
            self.file_send_lock.clear()
            self.run()
            
        except Exception as e:
            print(f"重启登录流程出错: {e}")
            QApplication.quit()

    def handle_file_message(self, msg):
        from_user = msg.get('from')
        file_id = msg.get('file_id')
        filename = msg.get('filename')
        size = msg.get('size')
        offline = msg.get('offline', False)
        if self.current_window:
            self.current_window.append_file_message(file_id, filename, size, is_self=False, sender_name=from_user)

    def download_file(self, file_id, filename):
        save_path, _ = QFileDialog.getSaveFileName(self.current_window, "保存文件", filename)
        if not save_path:
            return
        self.file_receivers[file_id] = {
            'filename': filename,
            'save_path': save_path,
            'file_handle': open(save_path, 'wb'),
            'received': 0
        }
        accept_msg = {"type": "file_accept", "file_id": file_id}
        self.send_json(accept_msg)
        msg = {"type": "file_download_request", "file_id": file_id, "filename": filename}
        self.send_json(msg)

    def handle_file_chunk(self, msg):
        file_id = msg.get('file_id')
        data_b64 = msg.get('data')
        chunk_data = base64.b64decode(data_b64)
        if file_id in self.file_receivers:
            info = self.file_receivers[file_id]
            info['file_handle'].write(chunk_data)
            info['received'] += len(chunk_data)

    def handle_file_complete(self, msg):
        file_id = msg.get('file_id')
        if file_id in self.file_receivers:
            info = self.file_receivers[file_id]
            try:
                if not info['file_handle'].closed:
                    info['file_handle'].close()
            except:
                pass
            QMessageBox.information(self.current_window, "文件接收完成", f"文件已保存到：{info['save_path']}")
            del self.file_receivers[file_id]
        else:
            QMessageBox.information(self.current_window, "文件发送完成", "文件已成功发送")

    def send_file(self, to_user, file_path, file_id):
        import time
        now = time.time()
        if to_user in self.file_send_lock and now - self.file_send_lock[to_user] < 3:
            return
        self.file_send_lock[to_user] = now

        if not os.path.exists(file_path):
            QMessageBox.warning(self.current_window, "错误", "文件不存在")
            return
        filename = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        file_msg = {
            "type": "file_message",
            "to": to_user,
            "file_id": file_id,
            "filename": filename,
            "size": size
        }
        self.send_json(file_msg)

        self.pending_files[file_id] = {
            'file_id': file_id,
            'to': to_user,
            'path': file_path,
            'size': size,
            'chunk_size': 64 * 1024,
            'chunks': (size + 64*1024 - 1) // (64*1024)
        }
        QTimer.singleShot(500, lambda: self._start_send_file_chunks(file_id))

    def _start_send_file_chunks(self, file_id):
        if file_id in self.pending_files:
            self._send_file_chunks(self.pending_files[file_id])
            del self.pending_files[file_id]

    def _send_file_chunks(self, file_info):
        file_id = file_info['file_id']
        path = file_info['path']
        chunk_size = file_info['chunk_size']
        with open(path, 'rb') as f:
            index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data_b64 = base64.b64encode(chunk).decode('ascii')
                chunk_msg = {
                    "type": "file_chunk",
                    "file_id": file_id,
                    "chunk_index": index,
                    "total_chunks": file_info['chunks'],
                    "data": data_b64
                }
                self.send_json(chunk_msg)
                index += 1
        complete_msg = {"type": "file_complete", "file_id": file_id}
        self.send_json(complete_msg)
        self.pending_file = None

if __name__ == "__main__":
    client = Client()
    client.run()
import os
import json
import base64
import time
from PyQt5.QtCore import QObject, QDateTime
from PyQt5.QtNetwork import QTcpSocket

def resolve_avatar_path(path, base_dir):
    if not path:
        return None
    # 尝试原始路径
    if os.path.isabs(path) and os.path.exists(path):
        return path
    if os.path.exists(path):
        return os.path.abspath(path)
    # 尝试相对于base_dir的路径
    abs_path = os.path.join(base_dir, path)
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
        base_dir,
        os.path.join(base_dir, 'avatars'),
        os.path.join(base_dir, 'server_files')
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

def make_grayscale(pixmap):
    from PyQt5.QtGui import QPixmap, QColor
    image = pixmap.toImage()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            gray = int(0.3 * color.red() + 0.59 * color.green() + 0.11 * color.blue())
            image.setPixelColor(x, y, QColor(gray, gray, gray))
    return QPixmap.fromImage(image)


class ClientHandler(QObject):
    def __init__(self, socket, server):
        super().__init__()
        self.socket = socket
        self.server = server
        self.username = None
        self.user_id = None
        self.address = socket.peerAddress().toString()

        self.socket.readyRead.connect(self.handle_ready_read)
        self.socket.disconnected.connect(self.handle_disconnected)
        self.server.log(f"新客户端连接: {self.address}")

    def handle_ready_read(self):
        while self.socket.bytesAvailable():
            line = self.socket.readLine()
            if not line:
                break
            data = line.data().decode('utf-8').strip()
            
            if not data:
                continue
                
            self.server.log(f"收到原始数据: {data}")
            try:
                msg = json.loads(data)
                self.process_message(msg)
            except Exception as e:
                self.server.log(f"消息解析错误: {e}")

    def process_message(self, msg):
        msg_type = msg.get('type')
        if msg_type == 'login':
            self.handle_login(msg)
        elif msg_type == 'register':
            self.handle_register(msg)
        elif msg_type == 'message':
            self.handle_message(msg)
        elif msg_type == 'logout':
            self.handle_logout()
        elif msg_type == 'friend_request':
            self.handle_friend_request(msg)
        elif msg_type == 'friend_request_response':
            self.handle_friend_request_response(msg)
        elif msg_type == 'search_users':
            self.handle_search_users(msg)
        elif msg_type == 'file_message':
            self.handle_file_message(msg)
        elif msg_type == 'file_chunk':
            self.handle_file_chunk(msg)
        elif msg_type == 'file_complete':
            self.handle_file_complete(msg)
        elif msg_type == 'file_download_request':
            self.handle_file_download_request(msg)
        elif msg_type == 'file_accept':
            self.handle_file_accept(msg)
        elif msg_type == 'file_reject':
            self.handle_file_reject(msg)

    def handle_login(self, msg):
        username = msg.get('username')
        password = msg.get('password')
        cursor = self.server.conn.cursor()

        # 查询用户基本信息（包含失败次数和锁定状态）
        cursor.execute("SELECT id, avatar, locked, login_failures FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        if not user:
            response = {"type": "login_response", "success": False, "message": "用户名或密码错误"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
            return

        user_id, avatar_path, locked, failures = user
        # 如果 failures 为 None，设为 0
        failures = failures or 0

        # 检查账号是否已被管理员锁定
        if locked == 1:
            response = {"type": "login_response", "success": False, "message": "用户已被锁定，请联系管理员"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
            return

        # 验证密码
        cursor.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        if cursor.fetchone():
            # 登录成功，重置失败次数
            cursor.execute("UPDATE users SET login_failures=0 WHERE id=?", (user_id,))
            self.server.conn.commit()

            # ===== 单点登录核心 =====
            if username in self.server.online_users:
                old_handler = self.server.online_users[username]
                kick_msg = {"type": "force_logout", "message": "您的账号在其他设备登录，您已被强制下线"}
                old_handler.socket.write((json.dumps(kick_msg) + "\n").encode('utf-8'))
                old_handler.socket.flush()
                del self.server.online_users[username]
                old_handler.socket.disconnectFromHost()
                self.server.log(f"用户 [{username}] 已在其他设备登录，旧连接被踢出")

            # 将新连接加入在线字典
            self.username = username
            self.user_id = user_id
            self.avatar_path = avatar_path
            self.server.online_users[username] = self

            # 返回登录成功响应
            response = {"type": "login_response", "success": True, "user_id": self.user_id, "avatar": self.avatar_path or ""}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))

            # 广播在线列表并发送好友列表
            self.server.broadcast_user_list()
            self.send_friend_list()
            self.send_offline_messages()
            self.send_pending_friend_requests()
            self.send_pending_files()

            self.server.log(f"用户 [{username}] 登录成功")
        else:
            # 密码错误，增加失败次数
            new_failures = failures + 1
            cursor.execute("UPDATE users SET login_failures=? WHERE id=?", (new_failures, user_id))
            self.server.conn.commit()

            if new_failures >= 3:
                # 锁定账号
                cursor.execute("UPDATE users SET locked=1 WHERE id=?", (user_id,))
                self.server.conn.commit()
                message = "连续登录失败超过3次，账号已被锁定"
                remaining = 0
            else:
                remaining = 3 - new_failures
                message = f"用户名或密码错误，您还有 {remaining} 次尝试机会"

            response = {
                "type": "login_response",
                "success": False,
                "message": message,
                "remaining_attempts": remaining
            }
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
            self.server.log(f"用户 [{username}] 登录失败，失败次数 {new_failures}")

    def handle_register(self, msg):
        username = msg.get('username')
        password = msg.get('password')
        encoding = msg.get('encoding', 'Base64')
        avatar = msg.get('avatar', '')
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            response = {"type": "register_response", "success": False, "message": "用户名已存在"}
        else:
            create_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            cursor.execute('''
                INSERT INTO users (username, avatar, password, encoding_rule, locked, create_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, avatar, password, encoding, 0, create_time))
            self.server.conn.commit()
            response = {"type": "register_response", "success": True}
        self.socket.write((json.dumps(response) + "\n").encode('utf-8'))

    def handle_message(self, msg):
        target = msg.get('to')
        content = msg.get('content')
        timestamp = msg.get('timestamp', QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))
        
        if target in self.server.online_users:
            target_handler = self.server.online_users[target]
            forward_msg = {
                "type": "message",
                "from": self.username,
                "to": target,
                "content": content,
                "timestamp": timestamp
            }
            target_handler.socket.write((json.dumps(forward_msg) + "\n").encode('utf-8'))
            self.server.log(f"消息转发: {self.username} -> {target}")
        else:
            # 目标不在线，存储离线消息
            cursor = self.server.conn.cursor()
            cursor.execute('''
                INSERT INTO offline_messages (from_user, to_user, content, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (self.username, target, content, timestamp))
            self.server.conn.commit()
            self.server.log(f"用户 [{target}] 不在线，消息已存储为离线")

    def handle_logout(self):
        if self.username:
            self.server.log(f"用户 [{self.username}] 主动注销")
            # 从在线用户列表中移除
            if self.username in self.server.online_users:
                del self.server.online_users[self.username]
                # 广播更新后的用户列表
                self.server.broadcast_user_list()
            # 从 handlers 列表中移除
            if self in self.server.handlers:
                self.server.handlers.remove(self)
            # 关闭 socket 连接
            self.socket.disconnectFromHost()
            # 清理用户名
            self.username = None

    def handle_friend_request(self, msg):
            target = msg.get('to')
            cursor = self.server.conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username=?", (target,))
            if not cursor.fetchone():
                response = {"type": "friend_request_response", "success": False, "message": "用户不存在"}
                self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
                return
            cursor.execute("SELECT 1 FROM friends WHERE user_id=? AND friend_id=?", 
                        (self.user_id, self.get_user_id_by_name(target)))
            if cursor.fetchone():
                response = {"type": "friend_request_response", "success": False, "message": "已经是好友"}
                self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
                return
            cursor.execute("SELECT id FROM friend_requests WHERE from_user=? AND to_user=? AND status='pending'", 
                        (self.username, target))
            if cursor.fetchone():
                response = {"type": "friend_request_response", "success": False, "message": "已发送过申请，请等待对方处理"}
                self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
                return
            request_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            cursor.execute('''
                INSERT INTO friend_requests (from_user, to_user, status, request_time)
                VALUES (?, ?, ?, ?)
            ''', (self.username, target, 'pending', request_time))
            self.server.conn.commit()
            if target in self.server.online_users:
                target_handler = self.server.online_users[target]
                notify_msg = {
                    "type": "friend_request_notify",
                    "from": self.username,
                    "request_time": request_time
                }
                target_handler.socket.write((json.dumps(notify_msg) + "\n").encode('utf-8'))
            response = {"type": "friend_request_response", "success": True, "message": "申请已发送"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))



    def handle_friend_request_response(self, msg):
        from_user = msg.get('from')
        agree = msg.get('agree')
        cursor = self.server.conn.cursor()
        # 查找待处理的申请
        cursor.execute('''
            SELECT id FROM friend_requests 
            WHERE from_user=? AND to_user=? AND status='pending'
        ''', (from_user, self.username))
        row = cursor.fetchone()
        if not row:
            response = {"type": "friend_request_response", "success": False, "message": "申请不存在或已处理"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
            return
        request_id = row[0]
        if agree:
            cursor.execute("UPDATE friend_requests SET status='accepted' WHERE id=?", (request_id,))
            from_id = self.get_user_id_by_name(from_user)
            to_id = self.user_id
            cursor.execute("INSERT INTO friends (user_id, friend_id) VALUES (?, ?)", (from_id, to_id))
            cursor.execute("INSERT INTO friends (user_id, friend_id) VALUES (?, ?)", (to_id, from_id))
            self.server.conn.commit()
            # 通知双方更新好友列表
            if from_user in self.server.online_users:
                from_handler = self.server.online_users[from_user]
                from_handler.send_friend_list()
            self.send_friend_list()
            response = {"type": "friend_request_response", "success": True, "message": "已添加好友"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
        else:
            cursor.execute("UPDATE friend_requests SET status='rejected' WHERE id=?", (request_id,))
            self.server.conn.commit()
            response = {"type": "friend_request_response", "success": True, "message": "已拒绝申请"}
            self.socket.write((json.dumps(response) + "\n").encode('utf-8'))
            # 通知发送者被拒绝
            if from_user in self.server.online_users:
                from_handler = self.server.online_users[from_user]
                from_handler.socket.write((json.dumps({"type": "friend_request_rejected", "from": self.username}) + "\n").encode('utf-8'))

    def get_user_id_by_name(self, username):
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        return row[0] if row else None

    def handle_search_users(self, msg):
        keyword = msg.get('keyword', '')
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT friend_id FROM friends WHERE user_id=?", (self.user_id,))
        friend_ids = [row[0] for row in cursor.fetchall()]
        query = "SELECT username, avatar FROM users WHERE username LIKE ? AND id != ?"
        params = (f"%{keyword}%", self.user_id)
        if friend_ids:
            query += " AND id NOT IN ({})".format(','.join(['?']*len(friend_ids)))
            params += tuple(friend_ids)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        users = [{"username": row[0], "avatar": row[1] or ""} for row in rows]
        response = {"type": "search_users_response", "users": users}
        self.socket.write((json.dumps(response) + "\n").encode('utf-8'))

    def send_pending_friend_requests(self):
        cursor = self.server.conn.cursor()
        cursor.execute('''
            SELECT from_user, request_time FROM friend_requests
            WHERE to_user = ? AND status = 'pending'
        ''', (self.username,))
        rows = cursor.fetchall()
        for from_user, request_time in rows:
            notify_msg = {"type": "friend_request_notify", "from": from_user, "request_time": request_time}
            self.socket.write((json.dumps(notify_msg) + "\n").encode('utf-8'))

    def send_friend_list(self):
        cursor = self.server.conn.cursor()
        cursor.execute('''
            SELECT u.username, u.avatar 
            FROM users u
            JOIN friends f ON u.id = f.friend_id
            WHERE f.user_id = ?
        ''', (self.user_id,))
        friends = []
        for username, avatar in cursor.fetchall():
            online = username in self.server.online_users
            friends.append({"username": username, "avatar": avatar or "", "online": online})
        msg = {"type": "friend_list", "friends": friends}
        self.socket.write((json.dumps(msg) + "\n").encode('utf-8'))

    def send_offline_messages(self):
        cursor = self.server.conn.cursor()
        cursor.execute('''
            SELECT from_user, content, timestamp FROM offline_messages
            WHERE to_user = ?
            ORDER BY id
        ''', (self.username,))
        messages = cursor.fetchall()
        for from_user, content, timestamp in messages:
            msg = {"type": "message", "from": from_user, "to": self.username, "content": content, "timestamp": timestamp}
            self.socket.write((json.dumps(msg) + "\n").encode('utf-8'))
        cursor.execute("DELETE FROM offline_messages WHERE to_user = ?", (self.username,))
        self.server.conn.commit()
        if messages:
            self.server.log(f"向用户 [{self.username}] 发送了 {len(messages)} 条离线消息")

    def handle_disconnected(self):
        if self.username:
            if self.username in self.server.online_users:
                del self.server.online_users[self.username]
            self.server.log(f"用户 [{self.username}] 断开连接")
            self.server.broadcast_user_list()
        else:
            self.server.log(f"未登录客户端断开连接: {self.address}")
        if self in self.server.handlers:
            self.server.handlers.remove(self)
        self.socket.deleteLater()

    def handle_file_message(self, msg):
        file_id = msg.get("file_id")
        sender = self.username
        receiver = msg.get("to")
        filename = msg.get("filename")
        size = msg.get("size")

        # 先检查数据库是否已存在该 file_id
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT id FROM offline_files WHERE file_id=?", (file_id,))
        if cursor.fetchone():
            self.server.log(f"文件 {file_id} 已存在，忽略重复消息")
            return

        # 插入数据库
        current_ts = int(time.time())
        cursor.execute("INSERT INTO offline_files (file_id, sender, receiver, filename, size, status, timestamp) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (file_id, sender, receiver, filename, size, current_ts))
        self.server.conn.commit()

        # 如果接收方在线，立即转发
        if receiver in self.server.online_users:
            target_handler = self.server.online_users[receiver]
            forward_msg = {
                "type": "file_message",
                "from": sender,
                "file_id": file_id,
                "filename": filename,
                "size": size
            }
            target_handler.socket.write((json.dumps(forward_msg) + "\n").encode('utf-8'))
            self.server.log(f"转发 file_message 给 {receiver}")
        else:
            self.server.log(f"目标 {receiver} 不在线，文件消息已存储")

    def handle_file_accept(self, msg):
        file_id = msg.get('file_id')
        cursor = self.server.conn.cursor()
        cursor.execute("UPDATE offline_files SET status='accepted' WHERE file_id=?", (file_id,))
        self.server.conn.commit()

        cursor.execute("SELECT sender FROM offline_files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()
        if row and row[0] in self.server.online_users:
            sender_handler = self.server.online_users[row[0]]
            accept_msg = {"type": "file_accept", "file_id": file_id}
            sender_handler.socket.write((json.dumps(accept_msg) + "\n").encode('utf-8'))

    def handle_file_reject(self, msg):
        file_id = msg.get('file_id')
        cursor = self.server.conn.cursor()
        cursor.execute("UPDATE offline_files SET status='rejected' WHERE file_id=?", (file_id,))
        self.server.conn.commit()

        cursor.execute("SELECT sender FROM offline_files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()
        if row and row[0] in self.server.online_users:
            sender_handler = self.server.online_users[row[0]]
            reject_msg = {"type": "file_reject", "file_id": file_id}
            sender_handler.socket.write((json.dumps(reject_msg) + "\n").encode('utf-8'))

    def handle_file_chunk(self, msg):
        file_id = msg.get('file_id')
        chunk_index = msg.get('chunk_index')
        data_b64 = msg.get('data')
        chunk_data = base64.b64decode(data_b64)
        tmp_path = os.path.join(self.server.file_storage_dir, f"{file_id}.tmp")
        mode = 'wb' if chunk_index == 0 else 'ab'
        with open(tmp_path, mode) as f:
            f.write(chunk_data)

    def handle_file_complete(self, msg):
        file_id = msg.get('file_id')
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT sender, receiver, filename FROM offline_files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()
        if not row:
            return
        sender, receiver, filename = row
        tmp_path = os.path.join(self.server.file_storage_dir, f"{file_id}.tmp")
        final_path = os.path.join(self.server.file_storage_dir, f"{file_id}_{filename}")
        if os.path.exists(tmp_path):
            os.rename(tmp_path, final_path)
            cursor.execute("UPDATE offline_files SET status='complete', file_path=? WHERE file_id=?", (final_path, file_id))
            self.server.conn.commit()
            self.server.log(f"文件已保存: {final_path}")
        else:
            self.server.log(f"临时文件不存在: {tmp_path}")

    def send_pending_files(self):
        cursor = self.server.conn.cursor()
        # 查询所有状态为 complete 的离线文件
        cursor.execute('''
            SELECT file_id, sender, filename, size FROM offline_files
            WHERE receiver = ? AND status = 'complete'
        ''', (self.username,))
        rows = cursor.fetchall()
        self.server.log(f"用户 {self.username} 登录，待推送离线文件数: {len(rows)}")
        for file_id, sender, filename, size in rows:
            # 发送通知
            msg = {"type": "file_message", "from": sender, "file_id": file_id, "filename": filename, "size": size, "offline": True}
            self.socket.write((json.dumps(msg) + "\n").encode('utf-8'))
            self.server.log(f"推送离线文件给 {self.username}: {filename}")
            # 更新状态为 notified，防止重复推送
            cursor.execute("UPDATE offline_files SET status='notified' WHERE file_id=? AND status='complete'", (file_id,))
            if cursor.rowcount == 0:
                self.server.log(f"警告：文件 {file_id} 状态不是 complete，可能已推送过")
            self.server.conn.commit()
        
    def handle_file_download_request(self, msg):
        file_id = msg.get('file_id')
        cursor = self.server.conn.cursor()
        cursor.execute("SELECT file_path, filename FROM offline_files WHERE file_id=?", (file_id,))
        row = cursor.fetchone()
        if not row:
            return
        file_path, filename = row
        if not file_path or not os.path.exists(file_path):
            self.server.log(f"文件不存在: {file_path}")
            return
        chunk_size = 64 * 1024
        with open(file_path, 'rb') as f:
            index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data_b64 = base64.b64encode(chunk).decode('ascii')
                chunk_msg = {"type": "file_chunk", "file_id": file_id, "chunk_index": index, "total_chunks": -1, "data": data_b64}
                self.socket.write((json.dumps(chunk_msg) + "\n").encode('utf-8'))
                index += 1
        complete_msg = {"type": "file_complete", "file_id": file_id, "filename": filename}
        self.socket.write((json.dumps(complete_msg) + "\n").encode('utf-8'))
        self.server.log(f"文件 {filename} 已发送完成")

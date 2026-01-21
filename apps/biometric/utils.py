import logging
import socket
from datetime import datetime
from pyzk2 import ZK

logger = logging.getLogger(__name__)

class BiometricConnection:
    def __init__(self, ip_address, port=4370, timeout=5):
        self.ip_address = ip_address
        self.port = int(port)
        self.zk = ZK(ip_address, port=self.port, timeout=timeout)
        self.conn = None

    def connect(self):
        try:
            self.conn = self.zk.connect()
            return True
        except Exception as e:
            logger.error(f"Error connecting to {self.ip_address}: {e}")
            return False

    def disconnect(self):
        if self.conn:
            try: self.conn.disconnect()
            except: pass

    def get_attendance(self):
        return self.conn.get_attendance() if self.conn else []

    def get_users(self):
        return self.conn.get_users() if self.conn else []

    def test_voice(self):
        if self.conn: self.conn.test_voice()
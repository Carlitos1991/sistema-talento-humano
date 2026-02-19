import logging
import socket
from datetime import datetime
from pyzk2 import ZK

logger = logging.getLogger(__name__)


class BiometricConnection:
    """Clase especializada para la comunicación con hardware ZKTeco."""

    def __init__(self, ip_address, port=4370, timeout=5):
        self.ip_address = ip_address
        self.port = int(port)
        self.timeout = timeout
        self.zk = ZK(self.ip_address, port=self.port, timeout=self.timeout, force_udp=False, ommit_ping=True)
        self.conn = None

    def connect(self):
        """Establece la conexión física con el dispositivo."""
        try:
            self.conn = self.zk.connect()
            return True
        except Exception as e:
            logger.error(f"Error conectando a {self.ip_address}: {e}")
            return False

    def get_time(self):
        """Lee la hora actual del hardware."""
        try:
            return self.conn.get_time() if self.conn else None
        except:
            return None

    def set_time(self, new_datetime):
        """Escribe una nueva hora en el hardware."""
        try:
            if self.conn:
                self.conn.set_time(new_datetime)
                return True
        except:
            return False
        return False

    def disconnect(self):
        """Cierra la conexión de forma segura."""
        if self.conn:
            try:
                self.conn.disconnect()
            except:
                pass
            self.conn = None

    def get_device_info(self):
        """Obtiene metadatos técnicos del dispositivo conectado."""
        if not self.conn:
            return None

        info = {}
        try:
            info['serialNumber'] = self.conn.get_serialnumber()
            info['deviceName'] = self.conn.get_device_name()
            info['firmware'] = self.conn.get_firmware_version()
            info['platform'] = self.conn.get_platform()
            # Obtenemos conteo de usuarios registrados
            users = self.conn.get_users()
            info['userCount'] = len(users) if users else 0
        except Exception as e:
            logger.warning(f"No se pudieron obtener todos los metadatos de {self.ip_address}: {e}")

        return info

    def get_attendance(self):
        """Descarga todas las marcaciones almacenadas en el equipo."""
        return self.conn.get_attendance() if self.conn else []

    def clear_attendance(self):
        """Borra la memoria de marcaciones (CUIDADO: Operación destructiva)."""
        if self.conn:
            self.conn.clear_attendance()

    def test_voice(self):
        """Ejecuta un sonido de prueba en el dispositivo."""
        if self.conn:
            self.conn.test_voice()


# apps/biometric/utils.py

def test_connection(ip_address, port=4370):
    result = {'success': False, 'message': '', 'device_info': None, 'error_details': None}

    # 1. Socket directo (TCP Handshake) - Esto ya lo tienes y es lo más fiable
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        sock.connect((ip_address, port))
        sock.close()
    except Exception as e:
        result['message'] = "Dispositivo inalcanzable"
        result['error_details'] = f"Error de red: {str(e)}"
        return result

    # 2. Conexión ZK - FORZAMOS UDP=False para evitar problemas de ping
    try:
        from pyzk2 import ZK
        zk = ZK(ip_address, port=port, timeout=5, force_udp=False, ommit_ping=True)  # <--- Forzar TCP
        conn = zk.connect()
        if conn:
            # Si conecta, sacamos la info
            info = {
                'serialNumber': conn.get_serialnumber(),
                'deviceName': conn.get_device_name(),
                'platform': conn.get_platform(),
                'firmware': conn.get_firmware_version(),
                'userCount': len(conn.get_users())
            }
            conn.disconnect()
            result['success'] = True
            result['device_info'] = info
            result['message'] = "Conexión exitosa"
        else:
            result['message'] = "Fallo de protocolo"
    except Exception as e:
        result['message'] = "Error de comunicación"
        result['error_details'] = str(e)

    return result

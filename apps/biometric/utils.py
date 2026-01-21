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
        self.zk = ZK(self.ip_address, port=self.port, timeout=self.timeout)
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


def test_connection(ip_address, port=4370):
    """
    Función de utilidad independiente para el botón 'Probar Conexión'.
    Realiza un 'ping' TCP rápido antes de intentar el protocolo ZK.
    """
    result = {
        'success': False,
        'message': '',
        'device_info': None,
        'error_details': None
    }

    # 1. Verificación rápida de Socket (TCP Handshake)
    # Esto evita que el servidor se quede colgado si la IP no existe
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)  # Timeout de 3 segundos para el socket

    try:
        sock.connect((ip_address, port))
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        result['message'] = "Dispositivo inalcanzable"
        result[
            'error_details'] = f"No hay respuesta en {ip_address}:{port}. Verifique la red o si el equipo está encendido."
        return result

    # 2. Intento de conexión vía Protocolo ZK
    bio = BiometricConnection(ip_address, port)
    if bio.connect():
        try:
            device_info = bio.get_device_info()
            bio.test_voice()

            result['success'] = True
            result['message'] = "Conexión establecida exitosamente."
            result['device_info'] = device_info
        except Exception as e:
            result['message'] = "Error de protocolo"
            result['error_details'] = str(e)
        finally:
            bio.disconnect()
    else:
        result['message'] = "Fallo de autenticación/protocolo"
        result['error_details'] = "El socket respondió, pero el protocolo ZKTeco falló. Verifique el puerto."

    return result

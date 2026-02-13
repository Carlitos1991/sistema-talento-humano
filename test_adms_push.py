import requests

# CONFIGURACIÓN
SERVER_URL = "http://localhost:4000/iclock/cdata"
SERIAL_NUMBER = "JUC5242600032"  # ¡PON EL MISMO DE TU DB!


def test_handshake():
    """Prueba el GET inicial que hace el dispositivo"""
    print(f"--- Probando Handshake (GET) ---")
    params = {
        'SN': SERIAL_NUMBER,
        'options': 'all',
        'pushver': '3.1.2'
    }
    try:
        response = requests.get(SERVER_URL, params=params)
        print(f"Estado: {response.status_code}")
        print(f"Respuesta: {response.text}")

        if "OK" in response.text:
            print("✅ HANDSHAKE EXITOSO")
        else:
            print("❌ ERROR EN HANDSHAKE")
    except Exception as e:
        print(f"Error de conexión: {e}")


def test_attendance_push():
    """Simula el envío de una marcación (POST)"""
    print(f"\n--- Probando Envío de Marcación (POST) ---")

    # Simulación de datos que envía el ZKTeco (Tab separated values)
    # ID_EN_BIO \t FECHA_HORA \t ESTADO \t TIPO
    body_data = f"1\t2026-02-13 08:30:00\t0\t1"

    params = {
        'SN': SERIAL_NUMBER,
        'table': 'ATTLOG'
    }

    try:
        response = requests.post(SERVER_URL, params=params, data=body_data)
        print(f"Estado: {response.status_code}")
        print(f"Respuesta: {response.text}")

        if "OK" in response.text:
            print("✅ MARCACIÓN RECIBIDA Y PROCESADA")
        else:
            print("❌ ERROR AL PROCESAR MARCACIÓN")
    except Exception as e:
        print(f"Error de conexión: {e}")


if __name__ == "__main__":
    test_handshake()
    test_attendance_push()
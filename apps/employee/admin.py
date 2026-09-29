from biometric.models import BiometricDevice, BiometricCommand
from employee.models import InstitutionalData

# 1. Configuración de datos
NUEVA_TARJETA = "7590185"
# Reemplaza con el nombre o IP de tu nuevo biométrico (destino)
NOMBRE_O_IP_DESTINO = "Bio 17"

# 2. Localizar tu usuario institucional
# Puedes buscar por tu número de cédula o tu ID biométrico
inst = InstitutionalData.objects.select_related('employee__person').filter(
    employee__person__document_number="1104898679"  # O biometric_id="TU_PIN"
).first()

if not inst:
    print("❌ No se encontró el registro institucional del empleado.")
else:
    pin = str(inst.biometric_id).strip()
    nombre = f"{inst.employee.person.first_name} {inst.employee.person.last_name}".strip()

    # 3. Localizar el biométrico nuevo (destino)
    target_device = BiometricDevice.objects.filter(
        name__icontains=NOMBRE_O_IP_DESTINO,
        is_active=True
    ).first()

    if not target_device:
        print("❌ No se encontró el biométrico destino.")
    else:
        # 4. Encolar el comando ADMS sobreescribiendo la tarjeta y asignando Admin (Pri=14)
        comando_adms = f"DATA UPDATE USERINFO PIN={pin}\tName={nombre}\tPri=14\tCard={NUEVA_TARJETA}"

        cmd = BiometricCommand.objects.create(
            device=target_device,
            command=comando_adms,
            status='PENDING'
        )

        print(f"✅ Comando ADMS #{cmd.id} encolado exitosamente:")
        print(f"   Destino: {target_device.name}")
        print(f"   Instrucción: {comando_adms}")
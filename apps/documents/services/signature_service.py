"""
Servicio Criptográfico para Certificados de Firma Electrónica (.p12 / .pfx).
Permite validar contraseñas en memoria, extraer vigencia e inspeccionar validez
sin comprometer la seguridad de las claves privadas.
"""

from datetime import datetime
from django.utils import timezone
from cryptography.hazmat.primitives.serialization import pkcs12


class SignatureService:

    @staticmethod
    def inspect_and_validate_p12(p12_bytes: bytes, password: str) -> dict:
        """
        Abre el archivo PKCS#12 en memoria con la contraseña provista.
        Retorna los metadatos del certificado o lanza ValueError si la clave es incorrecta
        o el formato no es válido.
        """
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password

        try:
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                p12_bytes,
                password_bytes
            )
        except Exception as e:
            raise ValueError("Contraseña incorrecta o archivo de firma dañado.") from e

        if not certificate:
            raise ValueError("El archivo no contiene un certificado de identidad digital válido.")

        # Extracción de vigencia
        not_before = certificate.not_valid_before_utc
        not_after = certificate.not_valid_after_utc

        now = timezone.now()
        if now > not_after:
            raise ValueError(f"El certificado de firma electrónica caducó el {not_after.strftime('%d/%m/%Y')}.")

        # Extracción de Subject y Emisor
        subject_components = [f"{attr.oid._name}={attr.value}" for attr in certificate.subject]
        issuer_components = [f"{attr.oid._name}={attr.value}" for attr in certificate.issuer]

        # Obtener CN o nombre representativo
        common_name = ""
        for attr in certificate.subject:
            if attr.oid._name == "commonName":
                common_name = attr.value
                break

        issuer_name = ""
        for attr in certificate.issuer:
            if attr.oid._name in ["commonName", "organizationName"]:
                issuer_name = attr.value
                break

        return {
            'common_name': common_name or ", ".join(subject_components[:2]),
            'subject_dn': ", ".join(subject_components),
            'issuer': issuer_name or ", ".join(issuer_components[:2]),
            'serial_number': str(certificate.serial_number),
            'valid_from': not_before,
            'valid_to': not_after,
        }

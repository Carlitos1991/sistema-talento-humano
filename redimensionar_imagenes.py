import os
from PIL import Image, ImageOps

# --- CONFIGURACIÓN ---
# Obtiene la ruta donde guardes este script
base_dir = os.path.dirname(os.path.abspath(__file__))

# Ruta exacta que indicaste: media/albums/images
input_folder = os.path.join(base_dir, 'media', 'albums', 'images')
output_folder = os.path.join(base_dir, 'media', 'albums', 'images_resized')

# TAMAÑO OBJETIVO
ANCHO = 80
ALTO = 88
# ---------------------

print(f"--- INICIANDO ---")
print(f"Script ubicado en: {base_dir}")
print(f"Buscando fotos en: {input_folder}")

if not os.path.exists(input_folder):
    print(f"\n[ERROR] No encuentro la carpeta 'media/albums/images'.")
    print("Asegúrate de guardar este script en la carpeta PRINCIPAL del proyecto (la que contiene la carpeta 'media').")
    exit()

# Crear carpeta de destino
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

contador = 0
errores = 0

print(f"\nProcesando imágenes a {ANCHO}x{ALTO} exactos...")

# Recorremos recursivamente por si hay subcarpetas dentro de 'images'
for root, dirs, files in os.walk(input_folder):
    # Mantener estructura de subcarpetas
    relative_path = os.path.relpath(root, input_folder)
    target_dir = os.path.join(output_folder, relative_path)

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for filename in files:
        if filename.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
            try:
                input_path = os.path.join(root, filename)
                output_path = os.path.join(target_dir, filename)

                with Image.open(input_path) as img:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    # Recorte exacto al centro (80x88)
                    new_img = ImageOps.fit(img, (ANCHO, ALTO), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                    new_img.save(output_path, quality=95)

                contador += 1
                if contador % 50 == 0:
                    print(f"Van {contador} fotos...")

            except Exception as e:
                print(f"Error en {filename}: {e}")
                errores += 1

print(f"\n¡TERMINADO!")
print(f"Procesadas: {contador}")
print(f"Errores: {errores}")
print(f"Las fotos nuevas están en: {output_folder}")
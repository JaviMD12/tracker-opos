import re
import sys
from pathlib import Path
try:
    import pypdf
except ImportError:
    print("Error: Necesitas instalar pypdf. Ejecuta en tu terminal: pip install pypdf")
    sys.exit(1)

# Configuracion
PDF_ORIGINAL = r"C:\Users\User\Desktop\Temario_Premium_Bomberos\proyecto_temario\rescate.pdf"
MD_GENERADO = r"C:\Users\User\Desktop\tracker-oposiciones\backend\Temarios_Premium\rescate.md"

def extraer_texto_pdf(ruta):
    texto = ""
    with open(ruta, "rb") as f:
        lector = pypdf.PdfReader(f)
        for pagina in lector.pages:
            texto += pagina.extract_text() + "\n"
    return texto

def encontrar_datos_clave(texto):
    datos = set()
    
    # 1. Buscar Leyes, Reales Decretos, Normativas (Ej: RD 2177/2004, Ley 31/1995)
    leyes = re.findall(r'(?i)(?:ley|rd|real decreto|decreto|resolución|norma)\s+\d+/\d{4}', texto)
    datos.update([l.upper() for l in leyes])
    
    # 2. Buscar cifras exactas con unidades críticas (Ej: 12 kN, 10.5 mm, 180 ºC, 40 kg)
    # Se ajusta para capturar espacios opcionales
    medidas = re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:kN|mm|cm|m|kg|ºC|C|bares|bar|V|kV)\b', texto)
    datos.update([m.lower().replace(" ", "") for m in medidas])
    
    # 3. Buscar porcentajes importantes (Ej: 75%, 80%)
    porcentajes = re.findall(r'\b\d+(?:[.,]\d+)?\s*%', texto)
    datos.update([p.replace(" ", "") for p in porcentajes])
    
    return datos

def main():
    if not Path(PDF_ORIGINAL).exists() or not Path(MD_GENERADO).exists():
        print(f"Por favor, ajusta las rutas en el código.\nPDF: {PDF_ORIGINAL}\nMD: {MD_GENERADO}")
        return

    print("Analizando PDF original...")
    texto_pdf = extraer_texto_pdf(PDF_ORIGINAL)
    claves_originales = encontrar_datos_clave(texto_pdf)
    
    print("Analizando Markdown generado...")
    texto_md = Path(MD_GENERADO).read_text(encoding="utf-8")
    
    # Normalizamos el texto generado para la busqueda
    texto_md_norm = texto_md.lower().replace(" ", "")
    texto_md_upper = texto_md.upper()
    
    faltan = []
    
    for dato in claves_originales:
        # Buscamos el dato en el MD generado
        # Para leyes buscamos en el texto en mayusculas, para medidas en el normalizado
        if dato.isupper():
            if dato not in texto_md_upper:
                faltan.append(f"[NORMATIVA] {dato}")
        else:
            if dato not in texto_md_norm:
                faltan.append(f"[DATO TÉCNICO/MEDIDA] {dato}")
                
    print("\n" + "="*50)
    print("🎯 REPORTE DE AUDITORÍA: DATOS POTENCIALMENTE PERDIDOS")
    print("="*50)
    if not faltan:
        print("¡Excelente! Todos los datos clave, leyes y medidas del PDF original están en tu Markdown.")
    else:
        print(f"ATENCIÓN: Se han detectado {len(faltan)} datos en el PDF original que no aparecen en el temario final:\n")
        for f in sorted(faltan):
            print(f" - {f}")
            
if __name__ == '__main__':
    main()

import os
import re
from collections import defaultdict
from pathlib import Path

DIR_ORIGEN = Path(__file__).resolve().parent / "conocimiento_ia"
DIR_SALIDA = Path(__file__).resolve().parent / "Temarios_Premium"

_PATRON_BLOQUE = re.compile(r"^(?P<tema>.+)_bloque_(?P<numero>\d+)\.txt$")

def main():
    temas = defaultdict(list)
    for ruta in DIR_ORIGEN.glob("*_bloque_*.txt"):
        match = _PATRON_BLOQUE.match(ruta.name)
        if match:
            temas[match.group("tema")].append((int(match.group("numero")), ruta))
    
    if not temas:
        print("No hay bloques para juntar.")
        return

    DIR_SALIDA.mkdir(exist_ok=True)
    
    for tema, bloques in temas.items():
        # Ordena los bloques numéricamente (1, 2, 3...)
        bloques_ordenados = sorted(bloques)
        contenido_total = []
        
        for _, ruta in bloques_ordenados:
            texto = ruta.read_text(encoding="utf-8").strip()
            if texto:
                contenido_total.append(texto)
                
        # Une todo con un par de saltos de línea entre bloques
        documento_final = f"# {tema.replace('_', ' ').title()}\n\n" + "\n\n".join(contenido_total)
        
        ruta_salida = DIR_SALIDA / f"{tema}.md"
        ruta_salida.write_text(documento_final, encoding="utf-8")
        print(f"[{tema}] Ensamblado gratis en {ruta_salida.name} ({len(bloques_ordenados)} bloques)")

if __name__ == "__main__":
    main()
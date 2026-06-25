"""
Script de diagnóstico para PDFs de cotizaciones del ERP de Grupo Jenta.

Uso: python diagnostico/check_pdf.py ruta/al/archivo.pdf

Analiza el PDF y determina si tiene texto seleccionable, extrae todos los valores
que parezcan precios, y recomienda si está listo para procesamiento automático
o si requiere OCR.

SafeToAutoRun: true
"""

import sys
import re
import pdfplumber


def extraer_texto_completo(pagina) -> str:
    """Extrae todo el texto de una página como string."""
    return pagina.extract_text() or ""


def extraer_palabras_con_coordenadas(pagina):
    """Extrae todas las palabras con sus coordenadas (x0, y0, x1, y1, text)."""
    palabras = pagina.extract_words()
    return [
        {
            "texto": p["text"],
            "x0": p["x0"],
            "y0": p["top"],
            "x1": p["x1"],
            "y1": p["bottom"],
        }
        for p in palabras
    ]


def extraer_tablas(pagina):
    """Intenta detectar tablas en la página."""
    try:
        tablas = pagina.extract_tables()
        return tablas
    except Exception:
        return []


# Patrón para detectar precios en formatos colombiano e internacional:
# - $1.500,00  (pesos colombianos)
# - 1,500.00   (formato internacional)
# - 1.500      (miles sin decimales)
# - 1500       (sin separadores)
PATRON_PRECIO = re.compile(r'[\$]?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?')


def detectar_precios(texto: str, palabras_con_coords: list):
    """
    Busca valores que parezcan precios en el texto y los correlaciona
    con sus coordenadas en la página.
    """
    resultados = []

    # Buscar en el texto completo con regex
    for match in PATRON_PRECIO.finditer(texto):
        valor_raw = match.group().strip()
        inicio = match.start()
        fin = match.end()

        # Determinar contexto (10 chars antes y después)
        ctx_inicio = max(0, inicio - 10)
        ctx_fin = min(len(texto), fin + 10)
        contexto = texto[ctx_inicio:ctx_fin].replace("\n", " ")

        # Intentar encontrar la palabra correspondiente en las coordenadas
        x0, y0, x1, y1 = None, None, None, None
        for p in palabras_con_coords:
            if p["texto"] == valor_raw or valor_raw.endswith(p["texto"]):
                x0 = p["x0"]
                y0 = p["y0"]
                x1 = p["x1"]
                y1 = p["y1"]
                break

        resultados.append({
            "valor_raw": valor_raw,
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "contexto": contexto,
        })

    return resultados


def analizar_formato(vaores_raw: list) -> str:
    """Analiza el patrón más común de formato numérico."""
    if not vaores_raw:
        return "No se detectaron valores"

    patrones = {
        "pesos_colombiano": 0,    # 1.500,00 o $1.500
        "internacional": 0,       # 1,500.00
        "entero_simple": 0,       # 1500
        "con_dolar": 0,           # $...
    }

    for v in vaores_raw:
        if v.startswith("$"):
            patrones["con_dolar"] += 1
        if "," in v and "." in v:
            if v.rfind(",") > v.rfind("."):
                patrones["pesos_colombiano"] += 1
            else:
                patrones["internacional"] += 1
        elif "," in v:
            patrones["pesos_colombiano"] += 1
        elif "." in v:
            patrones["internacional"] += 1
        else:
            patrones["entero_simple"] += 1

    return max(patrones, key=patrones.get)


def main():
    if len(sys.argv) < 2:
        print("Uso: python diagnostico/check_pdf.py ruta/al/archivo.pdf")
        sys.exit(1)

    ruta_pdf = sys.argv[1]

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            total_precios = 0
            texto_total = ""
            todos_precios = []

            print(f"Archivo: {ruta_pdf}")
            print(f"Páginas: {len(pdf.pages)}")
            print("-" * 60)

            for i, pagina in enumerate(pdf.pages):
                print(f"\n{'='*60}")
                print(f"PÁGINA {i + 1}")
                print(f"{'='*60}")

                # Extraer texto completo
                texto = extraer_texto_completo(pagina)
                texto_total += texto
                print(f"\n--- Texto completo ---")
                print(texto[:500] if texto else "(sin texto extraíble)")
                if len(texto) > 500:
                    print(f"... ({len(texto)} caracteres totales)")

                # Extraer palabras con coordenadas
                palabras = extraer_palabras_con_coordenadas(pagina)
                print(f"\n--- Palabras detectadas: {len(palabras)} ---")
                for p in palabras[:20]:
                    print(f"  ({p['x0']:.1f}, {p['y0']:.1f}) -> ({p['x1']:.1f}, {p['y1']:.1f}): '{p['texto']}'")
                if len(palabras) > 20:
                    print(f"  ... y {len(palabras) - 20} más")

                # Extraer tablas
                tablas = extraer_tablas(pagina)
                if tablas:
                    print(f"\n--- Tablas detectadas: {len(tablas)} ---")
                    for j, tabla in enumerate(tablas):
                        print(f"  Tabla {j + 1}: {len(tabla)} filas")
                        for fila in tabla[:5]:
                            print(f"    {fila}")
                        if len(tabla) > 5:
                            print(f"    ... y {len(tabla) - 5} filas más")

                # Detectar precios
                precios = detectar_precios(texto, palabras)
                todos_precios.extend(precios)

                if precios:
                    print(f"\n--- Precios detectados: {len(precios)} ---")
                    for p in precios:
                        coords = f"({p['x0']:.1f}, {p['y0']:.1f})" if p['x0'] else "(sin coord)"
                        print(f"  Valor: '{p['valor_raw']}'  Coord: {coords}")
                        print(f"  Contexto: '{p['contexto']}'")
                        print()
                else:
                    print("\n--- No se detectaron precios en esta página ---")

            # Resumen final
            print("\n" + "=" * 60)
            print("RESUMEN")
            print("=" * 60)

        # Filtrar solo precios reales (con $ o formato de miles con puntos o > 1000)
        precios_reales = [p for p in todos_precios if (
            p["valor_raw"].startswith("$")
            or (p["valor_raw"].count(".") >= 2 and "," in p["valor_raw"])
            or (len(p["valor_raw"].replace("$", "").replace(".", "").replace(",", "")) >= 5)
        )]

        texto_seleccionable = len(texto_total.strip()) > 0
        print(f"\nEl PDF tiene texto seleccionable? {'SI' if texto_seleccionable else 'NO'}")
        print(f"Valores tipo precio detectados (totales): {len(todos_precios)}")
        print(f"Precios reales (con formato moneda): {len(precios_reales)}")
        if precios_reales:
            print(f"Patron mas comun: {analizar_formato([p['valor_raw'] for p in precios_reales])}")
            print(f"\n--- PRECIOS REALES DETECTADOS ---")
            for p in precios_reales:
                coords = f"({p['x0']:.1f}, {p['y0']:.1f})" if p['x0'] else "(sin coord)"
                print(f"  {p['valor_raw']:>20s}  {coords}  ctx: '{p['contexto']}'")

        if texto_seleccionable and len(precios_reales) > 0:
            print("\n[RECOMENDACION] LISTO PARA FASE 1")
            print("   El PDF tiene texto seleccionable y se detectaron precios reales.")
            print("   Se puede proceder con la implementacion del motor de procesamiento.")
        elif texto_seleccionable and len(todos_precios) == 0:
            print("\n[RECOMENDACION] REVISAR PATRON DE PRECIOS")
            print("   El PDF tiene texto pero no se detectaron precios con el patron actual.")
        else:
            print("\n[RECOMENDACION] REQUIERE OCR")
            print("   El PDF no tiene texto seleccionable (es una imagen escaneada).")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{ruta_pdf}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error al procesar el PDF: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

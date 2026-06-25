"""
Motor seguro para procesar cotizaciones PDF y calcular valores con IVA.

Fase 1A:
- Lee un PDF con texto seleccionable.
- Detecta valores monetarios en formato colombiano.
- Clasifica valores dentro de la tabla principal cuando sea posible.
- Calcula el valor con IVA configurable.
- Por defecto NO modifica el PDF: solo genera reporte.
- Solo modifica el PDF cuando se usa --aplicar.
- No modifica totales generales en esta fase.

Uso recomendado en modo seguro:
python motor/procesar_pdf_iva.py samples/cotizacion_ejemplo.pdf output/reporte_iva.json --iva 19

Uso para generar PDF modificado:
python motor/procesar_pdf_iva.py samples/cotizacion_ejemplo.pdf output/reporte_iva.json --iva 19 --aplicar --salida-pdf output/cotizacion_con_iva.pdf --columnas "V. Unit,Valor Total"
"""

import argparse
import json
import re
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF


PATRON_NUMERO_COP = re.compile(
    r"^-?\d{1,3}(?:\.\d{3})+(?:,\d{2})?$"
)

PATRON_MONEDA_COMPLETA_COP = re.compile(
    r"^-?\$?\s?\d{1,3}(?:\.\d{3})+(?:,\d{2})?$"
)


@dataclass
class ValorMonetario:
    pagina: int
    texto_original: str
    valor_base: str
    valor_con_iva: str
    iva_aplicado: str
    x0: float
    y0: float
    x1: float
    y1: float
    columna_detectada: Optional[str]
    en_tabla_detalle: bool
    modificable: bool
    motivo: str


def normalizar_tasa_iva(valor: str) -> Decimal:
    """
    Convierte valores como '19', '19%', '0.19' en Decimal('0.19').
    """
    limpio = valor.replace("%", "").strip().replace(",", ".")

    try:
        tasa = Decimal(limpio)
    except InvalidOperation as exc:
        raise ValueError(f"Tasa de IVA inválida: {valor}") from exc

    if tasa > 1:
        tasa = tasa / Decimal("100")

    if tasa < 0:
        raise ValueError("La tasa de IVA no puede ser negativa.")

    return tasa


def parsear_pesos_colombianos(texto: str) -> Decimal:
    """
    Convierte '$1.250.000,00' o '1.250.000,00' en Decimal('1250000.00').
    """
    limpio = texto.strip()
    limpio = limpio.replace("$", "")
    limpio = limpio.replace(" ", "")

    negativo = limpio.startswith("-")
    limpio = limpio.replace("-", "")

    limpio = limpio.replace(".", "")
    limpio = limpio.replace(",", ".")

    try:
        valor = Decimal(limpio)
    except InvalidOperation as exc:
        raise ValueError(f"No se pudo convertir a moneda: {texto}") from exc

    if negativo:
        valor = valor * Decimal("-1")

    return valor


def formatear_pesos_colombianos(valor: Decimal) -> str:
    """
    Convierte Decimal('1487500.00') en '$1.487.500,00'.
    """
    valor = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negativo = valor < 0
    valor_abs = abs(valor)

    entero, decimales = f"{valor_abs:.2f}".split(".")

    grupos = []
    while entero:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]

    entero_formateado = ".".join(grupos)
    signo = "-" if negativo else ""

    return f"{signo}$ {entero_formateado},{decimales}"


def calcular_con_iva(valor: Decimal, tasa_iva: Decimal) -> Decimal:
    """
    Calcula valor + IVA usando Decimal.
    """
    return valor * (Decimal("1") + tasa_iva)


def es_numero_monetario_cop(texto: str) -> bool:
    """
    Determina si el texto parece un valor monetario colombiano.
    Se exige separador de miles para evitar confundir cantidades como 6,00 o 19.0.
    """
    texto = texto.strip()
    return bool(PATRON_NUMERO_COP.match(texto) or PATRON_MONEDA_COMPLETA_COP.match(texto))


def obtener_palabras_pagina(pagina) -> List[dict]:
    """
    Extrae palabras con coordenadas desde PyMuPDF.
    """
    palabras_raw = pagina.get_text("words")
    palabras = []

    for item in palabras_raw:
        x0, y0, x1, y1, texto = item[:5]
        bloque = item[5] if len(item) > 5 else 0
        linea = item[6] if len(item) > 6 else 0
        numero_palabra = item[7] if len(item) > 7 else 0

        palabras.append({
            "x0": float(x0),
            "y0": float(y0),
            "x1": float(x1),
            "y1": float(y1),
            "texto": str(texto).strip(),
            "bloque": bloque,
            "linea": linea,
            "numero_palabra": numero_palabra,
        })

    palabras.sort(key=lambda p: (p["bloque"], p["linea"], p["x0"]))
    return palabras


def unir_rectangulos(a: dict, b: dict) -> Tuple[float, float, float, float]:
    return (
        min(a["x0"], b["x0"]),
        min(a["y0"], b["y0"]),
        max(a["x1"], b["x1"]),
        max(a["y1"], b["y1"]),
    )


def extraer_tokens_monetarios(palabras: List[dict]) -> List[dict]:
    """
    Detecta valores monetarios.
    Soporta PDFs donde el símbolo '$' viene separado del número:
    '$' + '194.025,00'
    """
    tokens = []
    usados = set()

    for idx, palabra in enumerate(palabras):
        if idx in usados:
            continue

        texto = palabra["texto"]

        if texto in {"$", "-$"} and idx + 1 < len(palabras):
            siguiente = palabras[idx + 1]
            mismo_renglon = (
                palabra["bloque"] == siguiente["bloque"]
                and palabra["linea"] == siguiente["linea"]
            )

            if mismo_renglon and es_numero_monetario_cop(siguiente["texto"]):
                x0, y0, x1, y1 = unir_rectangulos(palabra, siguiente)
                signo = "-" if texto == "-$" else ""
                tokens.append({
                    "texto": f"{signo}$ {siguiente['texto']}",
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "bloque": palabra["bloque"],
                    "linea": palabra["linea"],
                })
                usados.add(idx)
                usados.add(idx + 1)
                continue

        if es_numero_monetario_cop(texto):
            tokens.append({
                "texto": texto,
                "x0": palabra["x0"],
                "y0": palabra["y0"],
                "x1": palabra["x1"],
                "y1": palabra["y1"],
                "bloque": palabra["bloque"],
                "linea": palabra["linea"],
            })
            usados.add(idx)

    return tokens


def agrupar_por_linea(palabras: List[dict]) -> Dict[Tuple[int, int], List[dict]]:
    grupos: Dict[Tuple[int, int], List[dict]] = {}

    for palabra in palabras:
        clave = (palabra["bloque"], palabra["linea"])
        grupos.setdefault(clave, []).append(palabra)

    for clave in grupos:
        grupos[clave].sort(key=lambda p: p["x0"])

    return grupos


def agrupar_por_bloque(palabras: List[dict]) -> Dict[int, List[dict]]:
    """
    Agrupa todas las palabras por bloque (no por línea).
    Útil cuando el encabezado de tabla está en líneas diferentes
    del mismo bloque.
    """
    grupos: Dict[int, List[dict]] = {}

    for palabra in palabras:
        clave = palabra["bloque"]
        grupos.setdefault(clave, []).append(palabra)

    for clave in grupos:
        grupos[clave].sort(key=lambda p: (p["linea"], p["x0"]))

    return grupos


def detectar_bloque_encabezado_tabla(palabras: List[dict]) -> Optional[Tuple[int, List[dict]]]:
    """
    Busca el bloque que contiene el encabezado de la tabla principal.
    Revisa todo el bloque (multi-línea) en busca de palabras clave
    como Referencia, Precio, IVA% y Valor.
    """
    bloques = agrupar_por_bloque(palabras)

    for bloque_id, palabras_bloque in bloques.items():
        textos_combinados = " ".join(sorted(
            set(p["texto"] for p in palabras_bloque),
            key=lambda t: t.lower(),
        )).lower()

        senales = 0
        if "referencia" in textos_combinados:
            senales += 1
        if "precio" in textos_combinados:
            senales += 1
        if "iva%" in textos_combinados or "iva" in textos_combinados:
            senales += 1
        if "valor" in textos_combinados:
            senales += 1

        if senales >= 3:
            return bloque_id, palabras_bloque

    return None


def detectar_linea_encabezado_tabla(palabras: List[dict]) -> Optional[List[dict]]:
    """
    Busca la línea de encabezado de la tabla principal (compatibilidad).
    Debe contener señales como Referencia, Precio, IVA% y Valor.
    """
    grupos = agrupar_por_linea(palabras)

    for linea in grupos.values():
        textos = [p["texto"] for p in linea]
        textos_normalizados = " ".join(textos).lower()

        tiene_referencia = "referencia" in textos_normalizados
        tiene_precio = "precio" in textos_normalizados
        tiene_iva = "iva%" in textos_normalizados or "iva" in textos_normalizados
        tiene_valor = "valor" in textos_normalizados

        if tiene_referencia and tiene_precio and tiene_iva and tiene_valor:
            return linea

    return None


def detectar_columnas_tabla(palabras: List[dict]) -> Dict[str, float]:
    """
    Detecta centros X de columnas relevantes en la tabla principal.
    Soporta dos estrategias:
      1. Encabezado en una sola línea (compatible con PDF muestras anteriores)
      2. Encabezado multi-línea en el mismo bloque (ej: PDF real de TEXCOL)
    """
    linea = detectar_linea_encabezado_tabla(palabras)

    if linea:
        columnas = {}

        definiciones = {
            "Precio Lista": ["Precio", "Lista"],
            "Costo": ["Costo"],
            "V. Unit": ["V.", "Unit"],
            "IVA%": ["IVA%"],
            "Valor Total": ["Valor", "Total"],
        }

        for nombre, secuencia in definiciones.items():
            rect = buscar_secuencia(linea, secuencia)
            if rect:
                x0, _y0, x1, _y1 = rect
                columnas[nombre] = (x0 + x1) / 2

        return columnas

    # Estrategia 2: encabezado multi-linea
    bloque_info = detectar_bloque_encabezado_tabla(palabras)
    if bloque_info is None:
        return {}

    bloque_id, palabras_bloque = bloque_info

    # Encontrar centro X de palabras clave dentro del bloque
    columnas = {}
    mapeo_columnas = {
        "Precio Lista": ["Precio", "Lista"],
        "V. Unit": ["V.", "Unit"],
        "IVA%": ["IVA%"],
        "Valor Total": ["Valor", "Total"],
    }

    for nombre, secuencia in mapeo_columnas.items():
        # Buscar la primera palabra de la secuencia en el bloque
        texto_buscar = secuencia[0].lower()
        candidatos = [p for p in palabras_bloque if p["texto"].strip().lower() == texto_buscar]

        if not candidatos:
            continue

        centro = (candidatos[0]["x0"] + candidatos[0]["x1"]) / 2
        columnas[nombre] = centro

    return columnas


def detectar_zona_tabla_detalle(palabras: List[dict]) -> Tuple[Optional[float], Optional[float]]:
    """
    Determina el rango vertical aproximado de la tabla principal de productos.
    Soporta encabezado en una línea o multi-línea en un bloque.
    """
    linea_encabezado = detectar_linea_encabezado_tabla(palabras)

    if linea_encabezado:
        inicio_y = max(p["y1"] for p in linea_encabezado)
    else:
        bloque_info = detectar_bloque_encabezado_tabla(palabras)
        if bloque_info is None:
            return None, None
        _bloque_id, palabras_bloque = bloque_info
        inicio_y = max(p["y1"] for p in palabras_bloque)

    posibles_finales = []
    for palabra in palabras:
        texto = palabra["texto"].strip().lower()
        if texto in {"total", "entrega:", "observaciones:", "sub", "items", "bruto"}:
            if palabra["y0"] > inicio_y:
                posibles_finales.append(palabra["y0"])

    # Buscar tambien "Total Items", "Sub Total", "Total Bruto", "+ Total IVA", "Total a Pagar"
    grupos = agrupar_por_linea(palabras)
    for linea in grupos.values():
        textos = " ".join(p["texto"] for p in linea).lower()
        for senial in ["total items", "sub total", "total bruto", "+ total iva", "total a pagar"]:
            if senial in textos:
                y_linea = min(p["y0"] for p in linea)
                if y_linea > inicio_y:
                    posibles_finales.append(y_linea)

    fin_y = min(posibles_finales) if posibles_finales else None
    return inicio_y, fin_y


def clasificar_columna(token: dict, columnas: Dict[str, float]) -> Optional[str]:
    """
    Clasifica un token monetario según la columna más cercana.
    """
    if not columnas:
        return None

    centro_x = (token["x0"] + token["x1"]) / 2
    columna_cercana = min(columnas.items(), key=lambda item: abs(item[1] - centro_x))
    nombre, centro = columna_cercana

    distancia = abs(centro - centro_x)

    if distancia <= 45:
        return nombre

    return None


def token_en_zona_detalle(token: dict, inicio_y: Optional[float], fin_y: Optional[float]) -> bool:
    if inicio_y is None:
        return False

    centro_y = (token["y0"] + token["y1"]) / 2

    if centro_y <= inicio_y:
        return False

    if fin_y is not None and centro_y >= fin_y:
        return False

    return True


def analizar_pdf(
    ruta_pdf: Path,
    tasa_iva: Decimal,
    columnas_modificables: List[str],
) -> List[ValorMonetario]:
    """
    Analiza el PDF y devuelve los valores monetarios detectados con su clasificación.
    """
    resultados: List[ValorMonetario] = []

    with fitz.open(str(ruta_pdf)) as documento:
        for indice_pagina, pagina in enumerate(documento, start=1):
            palabras = obtener_palabras_pagina(pagina)
            columnas = detectar_columnas_tabla(palabras)
            inicio_tabla_y, fin_tabla_y = detectar_zona_tabla_detalle(palabras)
            tokens = extraer_tokens_monetarios(palabras)

            for token in tokens:
                texto_original = token["texto"]
                columna = clasificar_columna(token, columnas)
                en_detalle = token_en_zona_detalle(token, inicio_tabla_y, fin_tabla_y)

                try:
                    valor_base_decimal = parsear_pesos_colombianos(texto_original)
                    valor_con_iva_decimal = calcular_con_iva(valor_base_decimal, tasa_iva)

                    modificable = (
                        en_detalle
                        and columna in columnas_modificables
                    )

                    if modificable:
                        motivo = "Valor dentro de tabla detalle y columna autorizada."
                    elif not en_detalle:
                        motivo = "No se modifica porque no está dentro de la tabla de detalle."
                    elif columna not in columnas_modificables:
                        motivo = "No se modifica porque la columna no está autorizada."
                    else:
                        motivo = "No se modifica por regla conservadora."

                    resultados.append(ValorMonetario(
                        pagina=indice_pagina,
                        texto_original=texto_original,
                        valor_base=formatear_pesos_colombianos(valor_base_decimal),
                        valor_con_iva=formatear_pesos_colombianos(valor_con_iva_decimal),
                        iva_aplicado=str(tasa_iva),
                        x0=round(token["x0"], 2),
                        y0=round(token["y0"], 2),
                        x1=round(token["x1"], 2),
                        y1=round(token["y1"], 2),
                        columna_detectada=columna,
                        en_tabla_detalle=en_detalle,
                        modificable=modificable,
                        motivo=motivo,
                    ))

                except Exception as exc:
                    resultados.append(ValorMonetario(
                        pagina=indice_pagina,
                        texto_original=texto_original,
                        valor_base="ERROR",
                        valor_con_iva="ERROR",
                        iva_aplicado=str(tasa_iva),
                        x0=round(token["x0"], 2),
                        y0=round(token["y0"], 2),
                        x1=round(token["x1"], 2),
                        y1=round(token["y1"], 2),
                        columna_detectada=columna,
                        en_tabla_detalle=en_detalle,
                        modificable=False,
                        motivo=f"Error al procesar valor: {exc}",
                    ))

    return resultados


def aplicar_reemplazos_pdf(
    ruta_entrada: Path,
    ruta_salida: Path,
    resultados: List[ValorMonetario],
) -> int:
    """
    Aplica reemplazos visuales únicamente a valores marcados como modificables.
    """
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    modificados = 0

    documento = fitz.open(str(ruta_entrada))

    for resultado in resultados:
        if not resultado.modificable:
            continue

        pagina = documento[resultado.pagina - 1]

        rect_original = fitz.Rect(
            resultado.x0,
            resultado.y0,
            resultado.x1,
            resultado.y1,
        )

        rect_cobertura = fitz.Rect(
            max(0, rect_original.x0 - 18),
            rect_original.y0 - 1,
            rect_original.x1 + 2,
            rect_original.y1 + 2,
        )

        pagina.draw_rect(
            rect_cobertura,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            overlay=True,
        )

        fontsize = max(6.5, min(8.5, rect_original.height * 0.72))

        pagina.insert_textbox(
            rect_cobertura,
            resultado.valor_con_iva,
            fontsize=fontsize,
            fontname="helv",
            color=(0, 0, 0),
            align=fitz.TEXT_ALIGN_RIGHT,
            overlay=True,
        )

        modificados += 1

    documento.save(
        str(ruta_salida),
        garbage=4,
        deflate=True,
    )
    documento.close()

    return modificados


def guardar_reporte(
    ruta_reporte: Path,
    ruta_pdf: Path,
    tasa_iva: Decimal,
    resultados: List[ValorMonetario],
    aplicar: bool,
    salida_pdf: Optional[Path],
    modificados: int,
) -> None:
    """
    Guarda reporte JSON auditable.
    """
    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "archivo_entrada": str(ruta_pdf),
        "iva": str(tasa_iva),
        "modo_aplicacion": "aplicar" if aplicar else "solo_reporte",
        "archivo_pdf_salida": str(salida_pdf) if salida_pdf else None,
        "total_valores_detectados": len(resultados),
        "total_valores_modificables": sum(1 for r in resultados if r.modificable),
        "total_valores_modificados": modificados,
        "resultados": [asdict(r) for r in resultados],
    }

    ruta_reporte.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Motor seguro para calcular IVA en valores monetarios de cotizaciones PDF."
    )

    parser.add_argument(
        "entrada_pdf",
        help="Ruta del PDF de entrada.",
    )

    parser.add_argument(
        "salida_reporte",
        help="Ruta del reporte JSON de salida.",
    )

    parser.add_argument(
        "--iva",
        default="19",
        help="Tasa de IVA. Ejemplos: 19, 19%%, 0.19. Default: 19.",
    )

    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Si se indica, genera PDF modificado. Si no se indica, solo genera reporte.",
    )

    parser.add_argument(
        "--salida-pdf",
        default=None,
        help="Ruta del PDF de salida. Obligatorio si se usa --aplicar.",
    )

    parser.add_argument(
        "--columnas",
        default="V. Unit,Valor Total",
        help="Columnas autorizadas para modificación, separadas por coma. Default: V. Unit,Valor Total.",
    )

    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()

    ruta_pdf = Path(args.entrada_pdf)
    ruta_reporte = Path(args.salida_reporte)
    salida_pdf = Path(args.salida_pdf) if args.salida_pdf else None

    if not ruta_pdf.exists():
        raise FileNotFoundError(f"No existe el PDF de entrada: {ruta_pdf}")

    if args.aplicar and salida_pdf is None:
        raise ValueError("Cuando uses --aplicar debes indicar --salida-pdf.")

    tasa_iva = normalizar_tasa_iva(args.iva)

    columnas_modificables = [
        columna.strip()
        for columna in args.columnas.split(",")
        if columna.strip()
    ]

    resultados = analizar_pdf(
        ruta_pdf=ruta_pdf,
        tasa_iva=tasa_iva,
        columnas_modificables=columnas_modificables,
    )

    modificados = 0

    if args.aplicar:
        modificados = aplicar_reemplazos_pdf(
            ruta_entrada=ruta_pdf,
            ruta_salida=salida_pdf,
            resultados=resultados,
        )

    guardar_reporte(
        ruta_reporte=ruta_reporte,
        ruta_pdf=ruta_pdf,
        tasa_iva=tasa_iva,
        resultados=resultados,
        aplicar=args.aplicar,
        salida_pdf=salida_pdf,
        modificados=modificados,
    )

    print("\nPROCESO FINALIZADO")
    print("-" * 60)
    print(f"PDF entrada: {ruta_pdf}")
    print(f"Reporte JSON: {ruta_reporte}")
    print(f"IVA aplicado para cálculo: {tasa_iva}")
    print(f"Valores detectados: {len(resultados)}")
    print(f"Valores modificables: {sum(1 for r in resultados if r.modificable)}")
    print(f"Valores modificados: {modificados}")

    if args.aplicar:
        print(f"PDF salida: {salida_pdf}")
    else:
        print("Modo seguro: no se modificó el PDF porque no se usó --aplicar.")


if __name__ == "__main__":
    main()

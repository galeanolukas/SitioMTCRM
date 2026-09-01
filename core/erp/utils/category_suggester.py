"""
Algoritmo híbrido para sugerir categorías automáticamente
basándose en los nombres de los productos.

Estrategia:
1. Diccionario de palabras clave predefinido → categoría
2. Para productos que no matchean el diccionario, análisis de frecuencia
   de palabras (sin stopwords) → las que aparecen en N+ productos son candidatas
3. El usuario revisa y confirma antes de aplicar
"""
from collections import Counter, defaultdict
import re

# Stopwords en español que no aportan info de categoría
STOPWORDS = frozenset({
    'de', 'del', 'la', 'el', 'las', 'los', 'en', 'con', 'sin', 'para', 'por',
    'al', 'a', 'y', 'o', 'u', 'un', 'una', 'unos', 'unas', 'x', 'c', 's',
    'c/', 's/', 'c/u', 'gr', 'grs', 'grs.', 'kg', 'kgs', 'cm', 'mts', 'mt',
    'lt', 'lts', 'ml', 'cc', 'mm', 'pza', 'pzas', 'und', 'unid', 'unidad',
    'caja', 'cajas', 'pack', 'set', 'kit', 'combo', 'promo', 'oferta',
    'nuevo', 'nueva', 'usado', 'usada', 'original', 'generico', 'generica',
    'gran', 'peque', 'chico', 'chica', 'mediano', 'mediana', 'grande',
    'color', 'negro', 'blanco', 'rojo', 'azul', 'verde', 'amarillo',
    'naranja', 'violeta', 'rosa', 'gris', 'marron', 'celeste',
    'c/u', 'pack', 'repuesto', 'rep', 'rep.',
    'talle', 'tamaño', 'medida', 'tipo', 'modelo', 'marca',
    'c/u.', 'sn', 's/n', 'n°', 'nro', 'num',
})

# Diccionario de palabras clave → nombre de categoría
# Se puede ampliar según el rubro (librería,tech, ferretería, etc.)
KEYWORD_DICT = {
    # Librería
    'LAPICERA': 'LAPICERAS',
    'BOLIGRAFO': 'LAPICERAS',
    'PEN': 'LAPICERAS',
    'FIBRA': 'FIBRAS Y MARCADORES',
    'MARKER': 'FIBRAS Y MARCADORES',
    'MARCADOR': 'FIBRAS Y MARCADORES',
    'RESALTADOR': 'FIBRAS Y MARCADORES',
    'HIGHLIGHTER': 'FIBRAS Y MARCADORES',
    'CUADERNO': 'CUADERNOS Y LIBRETAS',
    'LIBRETA': 'CUADERNOS Y LIBRETAS',
    'NOTAS': 'CUADERNOS Y LIBRETAS',
    'AGENDA': 'CUADERNOS Y LIBRETAS',
    'FOLDER': 'FOLDERS Y CARPETAS',
    'CARPETA': 'FOLDERS Y CARPETAS',
    'ARCHIVADOR': 'FOLDERS Y CARPETAS',
    'HOJA': 'HOJAS Y PAPELES',
    'HOJAS': 'HOJAS Y PAPELES',
    'PAPEL': 'HOJAS Y PAPELES',
    'RESMA': 'HOJAS Y PAPELES',
    'FOTOCOPIA': 'HOJAS Y PAPELES',
    'BOND': 'HOJAS Y PAPELES',
    'LAPIZ': 'LAPICES',
    'LAPIZ': 'LAPICES',
    'MINA': 'LAPICES',
    'GOMA': 'GOMAS Y SACAPUNTAS',
    'BORRADOR': 'GOMAS Y SACAPUNTAS',
    'SACAPUNTAS': 'GOMAS Y SACAPUNTAS',
    'TIJERA': 'TIJERAS Y CORTES',
    'TIJERAS': 'TIJERAS Y CORTES',
    'REGLA': 'REGLAS Y MEDICION',
    'ESCUADRA': 'REGLAS Y MEDICION',
    'COMPAS': 'REGLAS Y MEDICION',
    'PEGAMENTO': 'PEGAMENTOS Y ADHESIVOS',
    'GLUE': 'PEGAMENTOS Y ADHESIVOS',
    'CINTA': 'CINTAS Y ADHESIVOS',
    'TAPE': 'CINTAS Y ADHESIVOS',
    'STICKER': 'STICKERS Y ETIQUETAS',
    'ETIQUETA': 'STICKERS Y ETIQUETAS',
    'CALCULADORA': 'CALCULADORAS',
    'ABROCHADORA': 'ABROCHADORAS Y GRAPAS',
    'GRAPADORA': 'ABROCHADORAS Y GRAPAS',
    'GRAPA': 'ABROCHADORAS Y GRAPAS',
    'CLIP': 'CLIPS Y BULONES',
    'BULON': 'CLIPS Y BULONES',
    'PERFORADORA': 'PERFORADORAS',
    # Tecnología
    'MOUSE': 'ACCESORIOS PC',
    'TECLADO': 'ACCESORIOS PC',
    'AURICULAR': 'ACCESORIOS PC',
    'AURICULARES': 'ACCESORIOS PC',
    'CABLE': 'CABLES Y CONECTORES',
    'CARGADOR': 'CARGADORES Y FUENTES',
    'FUENTE': 'CARGADORES Y FUENTES',
    'PENDRIVE': 'ALMACENAMIENTO',
    'USB': 'ALMACENAMIENTO',
    'DISCO': 'ALMACENAMIENTO',
    'MEMORIA': 'ALMACENAMIENTO',
    'SD': 'ALMACENAMIENTO',
    # Ferretería
    'TORNILLO': 'TORNILLOS Y BULONES',
    'TORNILLOS': 'TORNILLOS Y BULONES',
    'CLAVO': 'CLAVOS Y PINZAS',
    'CLAVOS': 'CLAVOS Y PINZAS',
    'MARTILLO': 'HERRAMIENTAS MANUALES',
    'DESTORNILLADOR': 'HERRAMIENTAS MANUALES',
    'LLAVE': 'HERRAMIENTAS MANUALES',
    'ALICATE': 'HERRAMIENTAS MANUALES',
    'SIERRA': 'HERRAMIENTAS DE CORTE',
    'AMOLADORA': 'HERRAMIENTAS ELECTRICAS',
    'TALADRO': 'HERRAMIENTAS ELECTRICAS',
}


def tokenize(name):
    """Tokeniza un nombre de producto en palabras normalizadas."""
    if not name:
        return []
    # Mayúsculas, split por espacios y caracteres no alfanuméricos
    words = re.split(r'[\s\-_/()\.]+', name.upper().strip())
    # Filtrar vacíos, stopwords y números solos
    return [w for w in words if w and w not in STOPWORDS and not w.isdigit() and len(w) >= 2]


def suggest_categories(products, min_frequency=3):
    """
    Analiza una lista de productos y devuelve sugerencias de categorías.

    Args:
        products: QuerySet o lista de Product (debe tener .name y .id)
        min_frequency: mínima cantidad de productos para que una palabra sea categoría

    Returns:
        dict con:
          - 'suggestions': lista de {category_name, source, product_ids, product_count}
          - 'unmatched': lista de {product_id, product_name}
          - 'stats': {total_products, matched, unmatched, categories_suggested}
    """
    # Resultados
    suggestions = {}  # category_name -> {product_ids, source}
    unmatched = []

    # --- Paso 1: Diccionario ---
    for prod in products:
        tokens = tokenize(prod.name)
        matched = False
        for token in tokens:
            if token in KEYWORD_DICT:
                cat_name = KEYWORD_DICT[token]
                if cat_name not in suggestions:
                    suggestions[cat_name] = {'product_ids': set(), 'source': 'diccionario'}
                suggestions[cat_name]['product_ids'].add(prod.id)
                matched = True
                break  # primer match gana
        if not matched:
            unmatched.append(prod)

    # --- Paso 2: Frecuencia de palabras para los no matcheados ---
    word_products = defaultdict(set)  # word -> set de product_ids
    for prod in unmatched:
        tokens = tokenize(prod.name)
        for token in tokens:
            word_products[token].add(prod.id)

    # Palabras que aparecen en min_frequency+ productos
    freq_words = {w: pids for w, pids in word_products.items() if len(pids) >= min_frequency}

    # Crear sugerencias por frecuencia (pluralizar básico)
    for word, pids in sorted(freq_words.items(), key=lambda x: -len(x[1])):
        cat_name = _pluralize(word)
        # Evitar duplicar categoría del diccionario
        if cat_name not in suggestions:
            suggestions[cat_name] = {'product_ids': set(pids), 'source': 'frecuencia'}
        else:
            suggestions[cat_name]['product_ids'].update(pids)

    # Productos que siguen sin matchear
    matched_ids = set()
    for s in suggestions.values():
        matched_ids.update(s['product_ids'])
    truly_unmatched = [{'product_id': p.id, 'product_name': p.name} for p in products if p.id not in matched_ids]

    # Formatear salida
    result_suggestions = []
    for cat_name, info in sorted(suggestions.items(), key=lambda x: -len(x[1]['product_ids'])):
        result_suggestions.append({
            'category_name': cat_name,
            'source': info['source'],
            'product_ids': sorted(info['product_ids']),
            'product_count': len(info['product_ids']),
        })

    return {
        'suggestions': result_suggestions,
        'unmatched': truly_unmatched,
        'stats': {
            'total_products': len(products),
            'matched': len(matched_ids),
            'unmatched': len(truly_unmatched),
            'categories_suggested': len(result_suggestions),
        }
    }


def _pluralize(word):
    """Pluraliza básico en español."""
    word = word.upper()
    if word.endswith('A'):
        return word + 'S'
    elif word.endswith('O'):
        return word[:-1] + 'AS' if len(word) > 3 else word + 'S'
    elif word.endswith('Z'):
        return word[:-1] + 'CES'
    elif word.endswith('N'):
        return word[:-1] + 'NES'
    elif word.endswith('L') or word.endswith('R'):
        return word + 'ES'
    elif word.endswith('S') or word.endswith('X'):
        return word
    else:
        return word + 'S'

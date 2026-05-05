"""Familias / Rubros / Subrubros — taxonomía típica de almacén argentino.

Estructura: FAMILIAS define (codigo, nombre, orden).
RUBROS define (familia_codigo, codigo, nombre).
SUBRUBROS define (familia_codigo, rubro_codigo, codigo, nombre).

Los códigos son cortos (3 letras) para que queden legibles en el código del artículo
(patrón: {FAM3}-{RUB3}-{seq4}).
"""
from __future__ import annotations

FAMILIAS: list[tuple[str, str, int]] = [
    ("ALM", "Almacén", 10),
    ("LAC", "Lácteos y quesos", 20),
    ("FIA", "Fiambres y embutidos", 30),
    ("CAR", "Carnes", 40),
    ("PAN", "Panificados", 50),
    ("BSA", "Bebidas sin alcohol", 60),
    ("BCA", "Bebidas con alcohol", 70),
    ("LIM", "Limpieza", 80),
    ("HIG", "Higiene personal", 90),
    ("DRU", "Drugstore", 100),
    # Fallback para imports legacy (xls): codigo lowercase + hyphen es
    # intencional — `articulos_xls.build_fk_caches()` busca exactamente
    # `"sin-familia"`. Orden 999 lo deja siempre al final en cualquier sort.
    ("sin-familia", "Sin familia", 999),
]

# (fam, rubro_cod, nombre)
RUBROS: list[tuple[str, str, str]] = [
    # Almacén
    ("ALM", "ARR", "Arroz"),
    ("ALM", "FID", "Fideos"),
    ("ALM", "HAR", "Harinas"),
    ("ALM", "AZU", "Azúcares y endulzantes"),
    ("ALM", "YMA", "Yerbas y mates"),
    ("ALM", "LEG", "Legumbres"),
    ("ALM", "ACV", "Aceites y vinagres"),
    ("ALM", "CND", "Condimentos"),
    ("ALM", "CNS", "Conservas"),
    ("ALM", "DUL", "Dulces y mermeladas"),
    ("ALM", "GAL", "Galletitas"),
    ("ALM", "CER", "Cereales"),
    # Lácteos
    ("LAC", "LEC", "Leches"),
    ("LAC", "YOG", "Yogures"),
    ("LAC", "QUE", "Quesos"),
    ("LAC", "CRE", "Cremas y manteca"),
    ("LAC", "DLC", "Dulce de leche"),
    # Fiambres
    ("FIA", "JAM", "Jamones"),
    ("FIA", "SAL", "Salames y mortadelas"),
    ("FIA", "EMB", "Embutidos frescos"),
    # Carnes
    ("CAR", "POL", "Pollo"),
    ("CAR", "CER", "Cerdo"),
    ("CAR", "VAC", "Vacuno"),
    # Panificados
    ("PAN", "PAN", "Panes"),
    ("PAN", "FAC", "Facturas y medialunas"),
    ("PAN", "BUD", "Budines y bizcochos"),
    # Bebidas sin alcohol
    ("BSA", "GAS", "Gaseosas"),
    ("BSA", "AGU", "Aguas"),
    ("BSA", "JUG", "Jugos"),
    ("BSA", "ISO", "Isotónicas"),
    # Bebidas con alcohol
    ("BCA", "CER", "Cervezas"),
    ("BCA", "VIN", "Vinos"),
    ("BCA", "ESP", "Espumantes"),
    ("BCA", "LIC", "Licores y aperitivos"),
    ("BCA", "FER", "Fernet"),
    # Limpieza
    ("LIM", "DET", "Detergentes y lavavajilla"),
    ("LIM", "LAV", "Lavandinas y cloro"),
    ("LIM", "DES", "Desengrasantes"),
    ("LIM", "VID", "Limpiavidrios"),
    ("LIM", "ROP", "Cuidado de la ropa"),
    ("LIM", "PIS", "Limpiadores de piso"),
    # Higiene personal
    ("HIG", "SHA", "Shampoos y acondicionadores"),
    ("HIG", "JAB", "Jabones de tocador"),
    ("HIG", "DES", "Desodorantes"),
    ("HIG", "DEN", "Cuidado dental"),
    ("HIG", "PAP", "Papeles"),
    # Drugstore
    ("DRU", "PIL", "Pilas y lamparitas"),
    ("DRU", "BOL", "Bolsas y envases"),
    ("DRU", "PAP", "Papelería"),
    # Fallback para imports legacy (xls). `articulos_xls.build_fk_caches()`
    # lo busca via composite key (codigo, familia_id) bajo `sin-familia`.
    ("sin-familia", "sin-rubro", "Sin rubro"),
]

# (fam, rubro, sub_cod, nombre)
SUBRUBROS: list[tuple[str, str, str, str]] = [
    # Almacén / Arroz
    ("ALM", "ARR", "LFI", "Arroz Largo Fino"),
    ("ALM", "ARR", "INT", "Arroz Integral"),
    ("ALM", "ARR", "DOB", "Arroz Doble Carolina"),
    # Fideos
    ("ALM", "FID", "SEC", "Fideos Secos"),
    ("ALM", "FID", "HUE", "Fideos al Huevo"),
    ("ALM", "FID", "RIS", "Fideos Ristorante"),
    # Harinas
    ("ALM", "HAR", "000", "Harina 000"),
    ("ALM", "HAR", "004", "Harina 0000"),
    ("ALM", "HAR", "POL", "Harina de Polenta"),
    # Azúcares
    ("ALM", "AZU", "COM", "Azúcar Común"),
    ("ALM", "AZU", "IMP", "Azúcar Impalpable"),
    ("ALM", "AZU", "EDU", "Edulcorantes"),
    # Yerbas
    ("ALM", "YMA", "TRA", "Yerba Tradicional"),
    ("ALM", "YMA", "SUA", "Yerba Suave"),
    ("ALM", "YMA", "MCO", "Mate Cocido"),
    # Legumbres
    ("ALM", "LEG", "LEN", "Lentejas"),
    ("ALM", "LEG", "POR", "Porotos"),
    ("ALM", "LEG", "GAR", "Garbanzos"),
    # Aceites
    ("ALM", "ACV", "GIR", "Aceite de Girasol"),
    ("ALM", "ACV", "MEZ", "Aceite de Mezcla"),
    ("ALM", "ACV", "OLI", "Aceite de Oliva"),
    ("ALM", "ACV", "VIN", "Vinagres"),
    # Condimentos
    ("ALM", "CND", "SAL", "Sal"),
    ("ALM", "CND", "PIM", "Pimienta"),
    ("ALM", "CND", "ORE", "Orégano"),
    ("ALM", "CND", "AJO", "Ajo y Perejil"),
    # Conservas
    ("ALM", "CNS", "TOM", "Tomate en conserva"),
    ("ALM", "CNS", "ATU", "Atún y caballa"),
    ("ALM", "CNS", "ARV", "Arvejas y choclo"),
    # Dulces
    ("ALM", "DUL", "MER", "Mermeladas"),
    ("ALM", "DUL", "DMB", "Dulce de Membrillo"),
    ("ALM", "DUL", "MIE", "Miel"),
    # Galletitas
    ("ALM", "GAL", "DUL", "Galletitas Dulces"),
    ("ALM", "GAL", "SAL", "Galletitas Saladas"),
    ("ALM", "GAL", "REL", "Galletitas Rellenas"),
    ("ALM", "GAL", "OBL", "Obleas y barquillos"),
    # Cereales
    ("ALM", "CER", "COP", "Copos de Maíz"),
    ("ALM", "CER", "AVE", "Avena"),
    ("ALM", "CER", "GRA", "Granolas"),
    # Lácteos / Leches
    ("LAC", "LEC", "ENT", "Leche Entera"),
    ("LAC", "LEC", "DES", "Leche Descremada"),
    ("LAC", "LEC", "DLA", "Leche Deslactosada"),
    ("LAC", "LEC", "POL", "Leche en Polvo"),
    ("LAC", "LEC", "CHO", "Leche Chocolatada"),
    # Yogures
    ("LAC", "YOG", "BEB", "Yogur Bebible"),
    ("LAC", "YOG", "FIR", "Yogur Firme"),
    ("LAC", "YOG", "GRI", "Yogur Griego"),
    # Quesos
    ("LAC", "QUE", "DUR", "Queso Duro"),
    ("LAC", "QUE", "SEM", "Queso Semiduro"),
    ("LAC", "QUE", "BLA", "Queso Blando"),
    ("LAC", "QUE", "UNT", "Queso Untable"),
    ("LAC", "QUE", "RAL", "Queso Rallado"),
    # Cremas
    ("LAC", "CRE", "LEC", "Crema de Leche"),
    ("LAC", "CRE", "MAN", "Manteca"),
    ("LAC", "CRE", "MAR", "Margarinas"),
    # Dulce de leche
    ("LAC", "DLC", "FAM", "DDL Familiar"),
    ("LAC", "DLC", "REP", "DDL Repostero"),
    # Fiambres / Jamones
    ("FIA", "JAM", "COC", "Jamón Cocido"),
    ("FIA", "JAM", "CRU", "Jamón Crudo"),
    ("FIA", "JAM", "PAL", "Paleta"),
    ("FIA", "JAM", "LOM", "Lomito"),
    # Salames
    ("FIA", "SAL", "MIL", "Salame Milán"),
    ("FIA", "SAL", "COL", "Salame Colonia"),
    ("FIA", "SAL", "MOR", "Mortadela"),
    ("FIA", "SAL", "PAS", "Pastrón"),
    # Embutidos
    ("FIA", "EMB", "CHZ", "Chorizo"),
    ("FIA", "EMB", "MOR", "Morcilla"),
    ("FIA", "EMB", "SLC", "Salchichas"),
    # Carnes / Pollo
    ("CAR", "POL", "ENT", "Pollo Entero"),
    ("CAR", "POL", "PEC", "Pechuga"),
    ("CAR", "POL", "MUS", "Muslo"),
    ("CAR", "POL", "PMU", "Pata-Muslo"),
    ("CAR", "POL", "HIG", "Hígado"),
    # Cerdo
    ("CAR", "CER", "BON", "Bondiola"),
    ("CAR", "CER", "MAT", "Matambre de Cerdo"),
    ("CAR", "CER", "COS", "Costillar"),
    # Vacuno
    ("CAR", "VAC", "NLG", "Nalga"),
    ("CAR", "VAC", "ASA", "Asado"),
    ("CAR", "VAC", "MIL", "Milanesa"),
    # Panes
    ("PAN", "PAN", "LAC", "Pan Lactal"),
    ("PAN", "PAN", "MOL", "Pan de Molde"),
    ("PAN", "PAN", "FRA", "Pan Francés"),
    ("PAN", "PAN", "RAY", "Pan Rallado"),
    # Facturas
    ("PAN", "FAC", "MED", "Medialunas"),
    ("PAN", "FAC", "FAC", "Facturas Surtidas"),
    # Budines
    ("PAN", "BUD", "LIM", "Budín de Limón"),
    ("PAN", "BUD", "VAI", "Budín de Vainilla"),
    ("PAN", "BUD", "BIZ", "Bizcochuelos"),
    # Bebidas / Gaseosas
    ("BSA", "GAS", "COL", "Gaseosa Cola"),
    ("BSA", "GAS", "LLI", "Gaseosa Lima-Limón"),
    ("BSA", "GAS", "NAR", "Gaseosa Naranja"),
    ("BSA", "GAS", "TON", "Tónica"),
    ("BSA", "GAS", "POM", "Pomelo"),
    # Aguas
    ("BSA", "AGU", "MIN", "Agua Mineral"),
    ("BSA", "AGU", "SAB", "Agua Saborizada"),
    ("BSA", "AGU", "GAS", "Agua Gasificada"),
    # Jugos
    ("BSA", "JUG", "POL", "Jugo en Polvo"),
    ("BSA", "JUG", "LIS", "Jugo Listo"),
    ("BSA", "JUG", "CNC", "Jugo Concentrado"),
    # Isotónicas
    ("BSA", "ISO", "ISO", "Isotónicas"),
    # Cervezas
    ("BCA", "CER", "RUB", "Cerveza Rubia"),
    ("BCA", "CER", "NEG", "Cerveza Negra"),
    ("BCA", "CER", "ROJ", "Cerveza Roja"),
    # Vinos
    ("BCA", "VIN", "TIN", "Vino Tinto"),
    ("BCA", "VIN", "BLA", "Vino Blanco"),
    ("BCA", "VIN", "ROS", "Vino Rosado"),
    # Espumantes
    ("BCA", "ESP", "ESP", "Espumantes"),
    # Licores
    ("BCA", "LIC", "APE", "Aperitivos"),
    ("BCA", "LIC", "WIS", "Whisky"),
    ("BCA", "LIC", "RON", "Ron"),
    ("BCA", "LIC", "VOD", "Vodka"),
    # Fernet
    ("BCA", "FER", "CLA", "Fernet Clásico"),
    # Limpieza / Detergentes
    ("LIM", "DET", "LIQ", "Detergente Líquido"),
    ("LIM", "DET", "POL", "Detergente en Polvo"),
    ("LIM", "DET", "CAP", "Cápsulas Lavavajilla"),
    # Lavandina
    ("LIM", "LAV", "CLA", "Lavandina Común"),
    ("LIM", "LAV", "GEL", "Lavandina Gel"),
    # Desengrasantes
    ("LIM", "DES", "DES", "Desengrasantes"),
    # Limpiavidrios
    ("LIM", "VID", "VID", "Limpiavidrios"),
    # Ropa
    ("LIM", "ROP", "POL", "Jabón en Polvo"),
    ("LIM", "ROP", "LIQ", "Jabón Líquido"),
    ("LIM", "ROP", "SUA", "Suavizante"),
    # Pisos
    ("LIM", "PIS", "PER", "Limpiador Perfumado"),
    ("LIM", "PIS", "DES", "Limpiador Desinfectante"),
    # Higiene / Shampoo
    ("HIG", "SHA", "SHA", "Shampoo"),
    ("HIG", "SHA", "ACO", "Acondicionador"),
    ("HIG", "SHA", "CRE", "Crema de Enjuague"),
    # Jabones
    ("HIG", "JAB", "BAR", "Jabón en Barra"),
    ("HIG", "JAB", "LIQ", "Jabón Líquido"),
    # Desodorantes
    ("HIG", "DES", "AER", "Desodorante Aerosol"),
    ("HIG", "DES", "ROL", "Desodorante Roll-On"),
    # Dental
    ("HIG", "DEN", "PAS", "Pasta Dental"),
    ("HIG", "DEN", "CEP", "Cepillo Dental"),
    ("HIG", "DEN", "ENJ", "Enjuague Bucal"),
    # Papeles
    ("HIG", "PAP", "HIG", "Papel Higiénico"),
    ("HIG", "PAP", "TOA", "Toallas de Papel"),
    ("HIG", "PAP", "PAÑ", "Pañuelos"),
    # Drugstore / Pilas
    ("DRU", "PIL", "AA", "Pilas AA/AAA"),
    ("DRU", "PIL", "LAM", "Lamparitas LED"),
    # Bolsas
    ("DRU", "BOL", "RES", "Bolsas de Residuos"),
    ("DRU", "BOL", "FIL", "Film y Aluminio"),
    ("DRU", "BOL", "SER", "Servilletas"),
    # Papelería
    ("DRU", "PAP", "LAP", "Lápices y lapiceras"),
    ("DRU", "PAP", "CUA", "Cuadernos"),
]

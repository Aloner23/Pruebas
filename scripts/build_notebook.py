"""Construye y ejecuta notebooks/analisis_exploratorio.ipynb. Uso: python scripts/build_notebook.py"""

from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
md = nbformat.v4.new_markdown_cell
code = nbformat.v4.new_code_cell

cells = [
    md(
        "# Análisis exploratorio — flotilla Canadá 2023\n\n"
        "Este notebook cuenta la historia del archivo `data/raw/canada_2023_flotilla.csv`: qué contiene, "
        "qué tan completo está, qué se puede (y qué **no** se puede) concluir, y cómo se ve el reporte "
        "con un año completo usando datos **sintéticos claramente etiquetados**."
    ),
    code(
        "import sys\nfrom pathlib import Path\n\n"
        "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
        "sys.path.insert(0, str(ROOT))\n\n"
        "import pandas as pd\n"
        "from IPython.display import display\n\n"
        "from fleet_analytics import charts, synthetic\n"
        "from fleet_analytics.cleaning import coverage_matrix, load_raw, split_totals, to_long\n"
        "from fleet_analytics.metrics import (co2e_by_fuel, fuel_share, headline, monthly_trend,\n"
        "                                     segment_summary, with_unit_metrics)\n"
        "from fleet_analytics.validation import validate\n\n"
        "%matplotlib inline\n"
        "pd.set_option('display.float_format', '{:,.3f}'.format)\n"
        "pd.set_option('display.max_colwidth', 110)\n"
        "CSV = ROOT / 'data' / 'raw' / 'canada_2023_flotilla.csv'"
    ),
    md(
        "## 1. Inspección del archivo crudo\n\nSe lee todo como texto para no perder información (comas de miles, signos `$`)."
    ),
    code(
        "raw = load_raw(CSV)\n"
        "monthly, totals = split_totals(raw)\n"
        "print('Encoding: UTF-8 / ASCII puro (sin acentos ni BOM)')\n"
        "print('Filas totales:', len(raw), '| mensuales:', len(monthly), '| filas Total:', len(totals))\n"
        "print('Columnas:', raw.shape[1])\n"
        "value_cols = [c for c in raw.columns if c not in ['Month','Year','Country','Ownership','Type']]\n"
        "empty = (monthly[value_cols] == '').to_numpy().mean()\n"
        "print(f'Celdas numéricas vacías en filas mensuales: {empty:.1%}')\n"
        "raw.head(7)"
    ),
    md("### Cobertura: ¿qué segmento tiene datos en qué mes?"),
    code("cov = coverage_matrix(raw).astype(int)\ncov.columns = charts.MONTH_ABBR\ncov"),
    md(
        "**Lectura:** sólo 2 de 7 segmentos tienen datos. Los 5 segmentos de flota propia/arrendada "
        "(`owned, leased or renting`) están vacíos todo el año. *Logistic Operators (3PL) · tractor* "
        "sólo reporta enero–mayo. Y de los 6 combustibles del template sólo hay **diésel**."
    ),
    md(
        "## 2. Formato largo (tidy)\n\nUna fila por mes × segmento × combustible, sólo con combinaciones que tienen datos."
    ),
    code("long = to_long(raw)\nprint(long.shape)\nlong.head()"),
    md("## 3. Validación"),
    code("issues = validate(raw, long)\nprint(issues['severity'].value_counts().to_string())\nissues"),
    md(
        "**Hallazgos de calidad:**\n\n"
        "- No hay errores ni advertencias: los valores son positivos, completos, dentro de rangos plausibles, y la "
        "suma de los meses concilia con las filas `Total` del archivo.\n"
        "- **Rendimiento constante**: *route trucks* da exactamente 4.0000 km/L los 12 meses y el 3PL 2.2222 km/L "
        "(= 1/0.45 L/km) los 5 meses. Eso casi nunca ocurre con mediciones reales: sugiere que los litros (o los km) "
        "se **calcularon con un factor fijo**. Por lo tanto el rendimiento de este archivo *no* es un hallazgo "
        "operativo, es un supuesto de quien llenó el template.\n"
        "- El precio por litro de *route trucks* también es constante (1.3195 USD/L).\n"
        "- En el 3PL la columna general `Quantity` está vacía aunque `Diesel_Quantity` sí reporta vehículos."
    ),
    md("## 4. Métricas por segmento"),
    code(
        "summary = segment_summary(long)\n"
        "summary[['ownership','vehicle_type','fuel','months_reported','vehicles','km','volume','cost_usd',\n"
        "         'efficiency','l_per_100km','cost_per_km','cost_per_unit','km_per_vehicle','co2e_g_per_km']]"
    ),
    code("headline(long)"),
    md("## 5. Tendencias mensuales"),
    code(
        "m = with_unit_metrics(long)\n"
        "m['km_ratio_vs_min'] = m['km'] / m.groupby('vehicle_type')['km'].transform('min')\n"
        "m[['month_name','vehicle_type','vehicles','km','km_ratio_vs_min','cost_per_unit','km_per_vehicle','cost_per_km']]"
    ),
    code(
        "trend = monthly_trend(long, by=['ownership', 'vehicle_type'])\n"
        "fig = charts.monthly_by_segment(trend, 'km', 'km mensuales por segmento (datos reales)', 'km')"
    ),
    code(
        "fig = charts.monthly_by_segment(trend, 'cost_per_unit', 'Precio pagado por litro (datos reales)', 'USD/L', '${x:,.2f}')"
    ),
    md(
        "**Lectura de tendencias (datos reales):**\n\n"
        "- *Route trucks* (operadores independientes) sólo toma dos valores: 2,028,000 km o 2,535,000 km, exactamente "
        "×1.25. Es consistente con un cálculo de 507,000 km por semana × 4 o × 5 semanas (meses de 5 semanas: mayo, "
        "agosto, octubre y diciembre): de nuevo, **cifras estimadas**, no lecturas de odómetro.\n"
        "- *3PL tractor*: los km sí varían (2.44 M a 3.25 M) y el precio pagado por litro baja de 1.46 a 1.14 USD/L "
        "entre enero y mayo (−22 %). Con sólo 5 meses y litros derivados de los km, conviene confirmarlo con facturas.\n"
        "- Costo por km: el 3PL cuesta ~0.57 USD/km vs ~0.33 USD/km de route trucks, principalmente porque el factor "
        "de rendimiento supuesto es mucho menor (2.22 vs 4.0 km/L), coherente con tractocamiones vs camiones de reparto."
    ),
    md("## 6. Emisiones estimadas"),
    code("co2e_by_fuel(long)"),
    md(
        "Con el factor aproximado de 2.68 kg CO2e/L de diésel, el año reportado suma ~34,500 t CO2e "
        "(~17,700 t route trucks, ~16,800 t 3PL en sólo 5 meses). Es un **piso**: faltan 7 meses del 3PL y toda "
        "la flota propia."
    ),
    md(
        "## 7. Año completo con datos SINTÉTICOS\n\n"
        "> **Aviso:** todo lo que sigue usa `fleet_analytics.synthetic.generate()`. Son números inventados con el mismo "
        "formato del template para mostrar el comportamiento del reporte con 7 segmentos y 5 combustibles. "
        "Cada fila lleva `source = 'synthetic'`."
    ),
    code(
        "synth_raw = synthetic.generate(seed=42)\n"
        "synth = to_long(synth_raw, source='synthetic')\n"
        "print(synth['source'].unique(), synth.shape)\n"
        "fuel_share(synth, 'cost_usd')"
    ),
    code(
        "fig = charts.segment_bars(segment_summary(synth), 'co2e_g_per_km',\n"
        "                          'SINTÉTICO: intensidad de emisiones (g CO2e/km)', 'g CO2e/km', '{:,.0f}')"
    ),
    code(
        "fig = charts.monthly_total(monthly_trend(synth, by=[]), 'cost_per_km',\n"
        "                           'SINTÉTICO: costo por km de la flotilla', 'USD/km', '${x:,.3f}')"
    ),
    md(
        "## 8. Conclusiones\n\n"
        "1. El archivo real es un **template mayormente vacío**: 17 combinaciones mes-segmento con datos de 84, "
        "un solo combustible.\n"
        "2. Las cifras presentes parecen **estimaciones con factores fijos** (rendimiento y precio constantes, "
        "km en múltiplos semanales). Sirven para dimensionar orden de magnitud (≈40 M km, ≈12.9 M L, "
        "≈16.6 M USD, ≈34.5 kt CO2e) pero no para comparar eficiencia real.\n"
        "3. El valor del proyecto es el **pipeline**: limpieza robusta del template, validación explícita, métricas "
        "con definiciones claras y un reporte HTML reproducible que funcionará igual cuando el template se llene.\n\n"
        "Para generar los reportes: `python -m fleet_analytics report data/raw/canada_2023_flotilla.csv` y "
        "`python -m fleet_analytics report --synthetic`."
    ),
]

nb = nbformat.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
ExecutePreprocessor(timeout=120, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
out = ROOT / "notebooks" / "analisis_exploratorio.ipynb"
nbformat.write(nb, out)
print("Notebook ejecutado en", out)

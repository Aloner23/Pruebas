# Inspección del archivo real (`data/raw/canada_2023_flotilla.csv`)

Archivo original: `Canada_September (1) (1).csv` (renombrado). Todo lo que sigue se puede reproducir con
`python -m fleet_analytics validate data/raw/canada_2023_flotilla.csv` y en `notebooks/analisis_exploratorio.ipynb`.

## Estructura

| Aspecto | Valor |
|---|---|
| Encoding | ASCII puro (compatible UTF-8, sin BOM) |
| Filas | 91 + encabezado: 84 mensuales (12 meses × 7 segmentos) + 7 filas `Total` |
| Columnas | 30: 6 de identificación + 6 combustibles × 4 métricas |
| Formato numérico | Texto con separador de miles (`"2,028,000"`) y signo `$` (`"$668,987"`) |
| Celdas numéricas vacías (filas mensuales) | 96.2 % |

Segmentos (Ownership × Type): `owned, leased or renting` × {tractor, route trucks, supervision, executives, others},
`Independent Operators` × route trucks, `Logistic Operators (3PL)` × tractor.

Combustibles del template: Gasoline, Diesel, Ethanol, LPG(gas), NCG (gas) (se interpreta como gas natural
comprimido, GNC), Electric (en kWh). Métricas por combustible: km, litros/kWh, USD, cantidad de vehículos.

## Cobertura

| Segmento | Meses con datos | Combustible |
|---|---|---|
| Independent Operators · route trucks | 12 (ene–dic) | Diésel |
| Logistic Operators (3PL) · tractor | 5 (ene–may) | Diésel |
| owned, leased or renting · (5 tipos) | 0 | — |

Sólo 17 de 84 combinaciones mes-segmento tienen datos, y sólo de diésel.

## Hallazgos de calidad

1. **Sin errores de consistencia.** No hay negativos, ni km sin litros (o viceversa); los rangos de rendimiento
   y precio son plausibles para camiones diésel; la suma de los meses coincide con las filas `Total`.
2. **Rendimiento constante.** Route trucks: exactamente 4.0000 km/L en los 12 meses. 3PL: exactamente
   2.2222 km/L (= 0.45 L/km) en los 5 meses. Indica que una de las dos columnas se **derivó con un factor fijo**.
3. **Precio constante** en route trucks: 1.3195 USD/L todos los meses.
4. **km en dos valores** para route trucks: 2,028,000 u 2,535,000 (relación exacta 1.25 = 5/4), consistente
   con un estimado semanal × 4 o × 5 semanas, no con lecturas de odómetro.
5. **3PL:** los km sí varían (2.44 M – 3.25 M) y el precio por litro cae de 1.46 a 1.14 USD/L de enero a mayo.
   La columna general `Quantity` está vacía aunque `Diesel_Quantity` reporta 849–868 tractores.
6. **Filas `Total`** de segmentos sin datos vienen en `0` / `$0.00` (no vacías); se usan sólo para conciliar.

## Implicaciones

- Las cifras sirven para dimensionar orden de magnitud, no para evaluar eficiencia real.
- Los rendimientos (km/L) reflejan supuestos de quien llenó el template, no desempeño de la flota.
- El CO2e calculado (~34.5 kt) es un piso: faltan 7 meses del 3PL y toda la flota propia.

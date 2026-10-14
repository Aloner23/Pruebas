"""Factores de emisión aproximados (kg CO2e por unidad reportada).

IMPORTANTE: son aproximaciones de factores ampliamente publicados, pensadas para una
estimación de orden de magnitud, no para un inventario oficial de GEI. Para reportes
formales (p. ej. GHG Protocol / ISO 14064) se deben usar los factores vigentes del año,
país/provincia y tecnología del vehículo, incluyendo CH4 y N2O.

Fuentes de referencia (combustión en vehículos, CO2 dominante; CH4/N2O suman ~1-3 %):

* Gasolina ~2.31 kg CO2/L y diésel ~2.68 kg CO2/L: Environment and Climate Change Canada
  (ECCC), *National Inventory Report*, Anexo 6 (factores para gasolina ~2,307 g/L y diésel
  ~2,681 g/L). Coinciden con US EPA *GHG Emission Factors Hub* (8.78 kg/gal y 10.21 kg/gal
  -> ~2.32 y ~2.70 kg/L).
* GLP/propano ~1.51 kg CO2/L: ECCC NIR (propano ~1,515 g/L); US EPA 5.68 kg/gal -> ~1.50 kg/L.
* Etanol (E100): el CO2 de combustión es biogénico y bajo GHG Protocol se reporta por
  separado ("outside of scopes"); aquí se asume 0 kg CO2e fósil/L.
* Gas natural comprimido (columna "NCG" del template): ~1.9 kg CO2/m³ estándar (ECCC NIR).
  El template reporta "litros" sin aclarar la base. SUPUESTO: se interpretan como litros
  equivalentes de gasolina (GLE), la convención usual en estaciones de GNC de Norteamérica.
  Con ~34.7 MJ/L de gasolina y ~38 MJ/m³ de gas natural, 1 GLE ~ 0.91 m³ -> ~1.73 kg CO2e/GLE.
  Si la fuente reporta otra base (m³, kg), hay que cambiar este factor.
* Electricidad: ~0.12 kg CO2e/kWh, orden de magnitud del promedio de la red canadiense
  (ECCC NIR, intensidad de generación ~100-130 g/kWh en años recientes). Varía de <0.01
  (Quebec, Columbia Británica) a >0.5 (Alberta, Saskatchewan) según la provincia.
"""

from __future__ import annotations

EMISSION_FACTORS_KG_PER_UNIT: dict[str, float] = {
    "gasoline": 2.31,  # kg CO2e / L  (ECCC NIR ~2.307; EPA ~2.32)
    "diesel": 2.68,  # kg CO2e / L  (ECCC NIR ~2.681; EPA ~2.70)
    "ethanol": 0.0,  # kg CO2e fósil / L (biogénico, reportar aparte)
    "lpg": 1.51,  # kg CO2e / L  (ECCC NIR propano ~1.515)
    "cng": 1.73,  # kg CO2e / litro equivalente de gasolina (GLE) - SUPUESTO, ver arriba
    "electric": 0.12,  # kg CO2e / kWh (promedio Canadá, aproximado)
}

FACTOR_NOTES: dict[str, str] = {
    "gasoline": "ECCC NIR / US EPA, ~2.31 kg/L",
    "diesel": "ECCC NIR / US EPA, ~2.68 kg/L",
    "ethanol": "Biogénico: 0 kg fósil/L (reportar aparte)",
    "lpg": "ECCC NIR (propano), ~1.51 kg/L",
    "cng": "~1.9 kg/m3 (ECCC NIR) en base GLE ~1.73 kg/L (supuesto: unidad ambigua)",
    "electric": "Promedio red Canadá ~0.12 kg/kWh (varía por provincia)",
}

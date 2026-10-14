"""CLI: ``python -m fleet_analytics report data/raw/canada_2023_flotilla.csv``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fleet_analytics import synthetic
from fleet_analytics.cleaning import load_raw, to_long
from fleet_analytics.report import write_report
from fleet_analytics.validation import validate


def _cmd_report(args) -> int:
    if args.synthetic:
        raw = synthetic.generate(seed=args.seed)
        source, default_name = "synthetic", "reporte_sintetico.html"
    else:
        if not args.csv:
            print("Error: indique la ruta del CSV o use --synthetic", file=sys.stderr)
            return 2
        raw = load_raw(args.csv)
        source, default_name = "real", f"reporte_{Path(args.csv).stem}.html"
    out = Path(args.out) if args.out else Path(args.reports_dir) / default_name
    write_report(raw, out, source=source)
    if args.processed_dir:
        processed = Path(args.processed_dir)
        processed.mkdir(parents=True, exist_ok=True)
        stem = "sintetico" if args.synthetic else Path(args.csv).stem
        to_long(raw, source=source).to_csv(processed / f"{stem}_long.csv", index=False)
        validate(raw).to_csv(processed / f"{stem}_validacion.csv", index=False)
    print(f"Reporte ({source}) escrito en {out}")
    return 0


def _cmd_validate(args) -> int:
    issues = validate(load_raw(args.csv))
    if issues.empty:
        print("Sin hallazgos.")
    else:
        print(issues.to_string(index=False))
    return 1 if (issues["severity"] == "error").any() else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet_analytics", description="Analítica de energía de flotillas")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="Genera un reporte HTML autocontenido")
    rep.add_argument("csv", nargs="?", help="Ruta al CSV con el formato del template")
    rep.add_argument("--synthetic", action="store_true", help="Usa datos SINTÉTICOS etiquetados (ignora csv)")
    rep.add_argument("--seed", type=int, default=42, help="Semilla del generador sintético")
    rep.add_argument("--out", help="Ruta del HTML de salida")
    rep.add_argument("--reports-dir", default="reports", help="Carpeta de salida por defecto")
    rep.add_argument(
        "--processed-dir", default="data/processed", help="Dónde guardar el CSV largo y la validación ('' para omitir)"
    )
    rep.set_defaults(func=_cmd_report)

    val = sub.add_parser("validate", help="Imprime los hallazgos de validación (exit 1 si hay errores)")
    val.add_argument("csv")
    val.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

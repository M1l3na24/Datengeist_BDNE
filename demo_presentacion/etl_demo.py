"""
etl_demo.py — Datengeist Demo
ETL mini con arquitectura medallón:
  BRONCE → extrae 6 tablas de PostgreSQL datengeist_demo
  PLATA  → desnormaliza en ventas_completas + catálogo + perfiles
  ORO    → agrega 7 colecciones KPI en MongoDB datengeist_demo

Ejecutar: python demo/etl_demo.py
"""

import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).parent


def run_etl():
    scripts = [
        DEMO_DIR / 'bronce.py',
        DEMO_DIR / 'plata.py',
        DEMO_DIR / 'oro.py',
    ]
    for script in scripts:
        result = subprocess.run([sys.executable, str(script)])
        if result.returncode != 0:
            sys.exit(result.returncode)

    print('\n  ⟶  Siguiente: python indices.py')


if __name__ == '__main__':
    run_etl()

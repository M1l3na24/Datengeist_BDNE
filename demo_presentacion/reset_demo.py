"""
reset_demo.py — Datengeist Demo
Vacía PostgreSQL y MongoDB datengeist_demo y regenera los datos base con setup_demo.py.
El ETL (bronce, plata, oro) y los índices se corren manualmente después.

Uso: python reset_demo.py
"""

import os
import sys
import subprocess

from pymongo import MongoClient
from sqlalchemy import create_engine, text

DEMO_DIR     = os.path.dirname(os.path.abspath(__file__))
SETUP_SCRIPT = os.path.join(DEMO_DIR, 'setup_demo.py')

PG_DEMO   = 'postgresql+psycopg2://admin:cuyos123@127.0.0.1:5433/datengeist_demo'
MONGO_URI = 'mongodb://admin:cuyos123@localhost:27017/?authSource=admin'
MONGO_DB  = 'datengeist_demo'


def banner(texto):
    print('\n' + '*-' * 30)
    print(f'  {texto}')
    print('*-' * 30)


def step(texto):
    print(f'\n  ⟶  {texto}')


def ok(texto):
    print(f'  ok:  {texto}')


def main():
    banner('Datengeist — Reset del Entorno Demo')
    print('  Esto borra SOLO datengeist_demo. Producción no se toca.')

    # 1. Limpiar PostgreSQL
    step('Limpiando PostgreSQL datengeist_demo...')
    try:
        engine = create_engine(PG_DEMO, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(text(
                'TRUNCATE TABLE detalle_ventas, ventas, operaciones_y_personal, '
                'variables_externas, dim_clientes_y_segmentos, dim_productos_y_sabores CASCADE'
            ))
        engine.dispose()
        ok('Tablas vaciadas')
    except Exception as e:
        print(f'  ℹ   PostgreSQL: {e}')
        print('      (La base se creará en el siguiente paso)')

    # 2. Limpiar MongoDB
    step('Limpiando MongoDB datengeist_demo...')
    try:
        mongo = MongoClient(MONGO_URI)
        colecciones = mongo[MONGO_DB].list_collection_names()
        if colecciones:
            for col in colecciones:
                mongo[MONGO_DB][col].drop()
            ok(f'{len(colecciones)} colecciones eliminadas')
        else:
            ok('MongoDB datengeist_demo ya estaba vacío')
        mongo.close()
    except Exception as e:
        print(f'  MongoDB: {e}')

    # 3. Regenerar datos base en PostgreSQL
    step('Ejecutando setup_demo.py...')
    result = subprocess.run([sys.executable, SETUP_SCRIPT])
    if result.returncode != 0:
        print('\n  setup_demo.py falló. Revisa el error arriba.')
        sys.exit(1)

    # 4. Confirmación
    banner('Listo — datos base regenerados')
    print('  Siguiente paso: correr el ETL manualmente')
    print()
    print('  python bronce.py')
    print('  python plata.py')
    print('  python oro.py')
    print('  python indices.py')
    print('  python inyectar_ventas.py')
    print('*-' * 30 + '\n')


if __name__ == '__main__':
    main()

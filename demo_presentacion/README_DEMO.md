# README_DEMO.md — Datengeist Demo en Vivo

---

## Estructura de la demo

```
demo/
├── setup_demo.py       ← Paso 1: genera datos base en PostgreSQL
├── bronce.py           ← Paso 2: extrae tablas de PostgreSQL a Parquet
├── plata.py            ← Paso 3: transforma → 3 colecciones base en MongoDB
├── oro.py              ← Paso 4: agrega → 8 colecciones KPI en MongoDB
├── indices.py          ← Paso 5: crea índices en todas las colecciones
├── inyectar_ventas.py  ← Paso 6: simula 5 ventas en tiempo real
├── reset_demo.py       ← Reset: vacía todo y regenera datos base
├── etl_demo.py         ← Alternativa: ejecuta bronce → plata → oro en secuencia
├── requirements_demo.txt
└── README_DEMO.md      ← Este archivo
```

---

## Entorno demo vs. la conectada al tablero

| Aspecto              | Tablero          | Demo                        |
|----------------------|----------------------|-----------------------------|
| PostgreSQL DB        | `datengeist`         | `datengeist_demo`           |
| MongoDB DB           | `datengeist`         | `datengeist_demo`           |
| Contenedores         | Los mismos           | Los mismos                  |
| Tickets              | ~1,224,266           | ~1,800                      |
| Período              | 2021–2024 (4 años)   | Oct 2024–Mar 2025 (6 meses) |
| Clientes             | 3,000                | 5 (con nombres reales)      |
| Sabores              | 15                   | 10                          |

**Los contenedores de producción NO se tocan.** El demo usa las mismas
credenciales (admin/cuyos123) pero distintas bases de datos.

---

## Clientes del demo

| # | Nombre                    | Segmento  | Giro        | Sabor favorito |
|---|---------------------------|-----------|-------------|----------------|
| 1 | Restaurante El Sabor      | VIP       | Restaurante | Tamarindo      |
| 2 | María González            | Frecuente | Familiar    | Vainilla       |
| 3 | Pastelería La Dulce Vida  | Frecuente | Cafetería   | Chocolate      |
| 4 | Colegio Benito Juárez     | Ocasional | Corporativo | Fresa          |
| 5 | Juan Ramírez              | Nuevo     | Particular  | Mango          |

---

## Sabores disponibles en el demo (10 de 15)

Vainilla · Chocolate · Fresa · Mango · Limón · Pistache · Nuez · Cajeta · Tamarindo · Coco

---

## Flujo:

### 0. Verificar que los contenedores están corriendo

La demo usa los mismos contenedores del proyecto principal. Verifica que estén activos:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "sql_server|mongodb"
```

Deben aparecer `sql_server_contenedor` y `mongodb_datengeist` con estado `Up`.
Si no están corriendo, levántalos desde la raíz del proyecto:

```bash
docker compose start
```

---

### 1. Prepara el entorno

```bash
cd demo_presentacion
source venv/bin/activate

# Solo la primera vez (o después de reset_demo.py)
python setup_demo.py
```

Esto crea la base `datengeist_demo` en PostgreSQL con:
- 6 tablas con ~1,800 tickets de Oct 2024–Mar 2025
- Festivos: Halloween, Día de Muertos, Revolución, Navidad, Año Nuevo, Constitución, Benito Juárez

---

### 2. Correr el ETL capa por capa

```bash
python bronce.py
python plata.py
python oro.py
```

- **BRONCE:** extrae las 6 tablas de PostgreSQL a Parquet
- **PLATA:** desnormaliza y enriquece → `ventas_completas`, `catalogo_productos`, `clientes_perfil`
- **ORO:** agrega → 8 colecciones KPI en MongoDB

---

### 3. Crear índices en MongoDB

```bash
python indices.py
```

Crea índices en las 11 colecciones. Muestra en vivo cuántos índices se registran
por colección.

---

### 4. Inyectar ventas en vivo

```bash
# Corre el ETL después de cada venta
python inyectar_ventas.py

# Corre el ETL una sola vez al final
python inyectar_ventas.py --rapido
```

El script simula 5 ventas y las inserta directamente en PostgreSQL.
Al terminar corre el ETL automáticamente y muestra el conteo de documentos
por colección en MongoDB para confirmar que los datos llegaron.

---

### 5. Resetear para repetir la demo

```bash
python reset_demo.py
```

Borra `datengeist_demo` en PostgreSQL y MongoDB y regenera todo desde cero.
Permite repetir la demo cuantas veces sea necesario.

---

## Diagrama del flujo de datos

```
┌─────────────────────────────────────────────────────────┐
│                   setup_demo.py                         │
│   Genera datos sintéticos → PostgreSQL datengeist_demo  │
│   (5 clientes, 10 sabores, ~1,800 tickets, 6 meses)     │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                    etl_demo.py                          │
│   BRONCE: extrae 6 tablas de PostgreSQL → Parquet       │
│   PLATA:  desnormaliza → 3 colecciones base             │
│   ORO:    agrega → 8 colecciones KPI en MongoDB demo    │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                  inyectar_ventas.py                     │
│   Simula 5 ventas → PostgreSQL                          │
│   → ETL incremental → MongoDB actualizado               │
│   → Muestra conteo de docs por colección                │
└─────────────────────────────-───────────────────────────┘
```
---

## Problemas comunes

| Problema | Solución |
|---|---|
| "Connection refused" en PostgreSQL | Verificar que Docker corre: `docker ps` |
| MongoDB no acepta conexión | Usar IP del contenedor: `docker inspect mongodb_datengeist \| grep IPAddress` |
| Metabase no muestra la colección | Esperar 30 seg y hacer "Sync database" en Admin |
| Error de permisos en datengeist_demo | El usuario `admin` ya tiene permisos globales |
| `ModuleNotFoundError` | Activar venv: `source venv/bin/activate` |

---

## Comandos de referencia rápida

```bash
# Verificar contenedores (deben estar Up antes de correr la demo)
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "sql_server|mongodb"

# Para ahorrar recursos
docker stop metabase_datengeist
docker start metabase_datengeist

# Activar entorno y entrar a la carpeta
source venv/bin/activate
cd demo_presentacion

# Instala lo necesario
pip install -r requirements_demo.txt

# Demo completa
python setup_demo.py
python bronce.py
python plata.py
python oro.py
python indices.py
python inyectar_ventas.py         # ETL por cada venta
python inyectar_ventas.py --rapido  # ETL al final

# Resetear
python reset_demo.py
```

---

## Archivos del proyecto principal (NO modificar)

```
datengeist.sql    ← esquema PostgreSQL de producción
generador.py      ← genera 1.2M tickets en producción
etl.py            ← ETL de producción
predictor.py      ← modelo ML de producción
```

Todos los scripts de demo son independientes y no importan ni modifican
estos archivos ni el tablero en METABASE.


---

## Comandos para ejecutar siempre que terminemos una demo para iniciar de 0 la  próxima vez

1. Elimina la base de datos en PostgreSQL
  
  docker exec -it sql_server_contenedor psql -U admin -d postgres -c "DROP DATABASE IF EXISTS datengeist_demo;"

2. Eliminar la base de datos en MongoDB
  
  docker exec -it mongodb_datengeist mongosh -u admin -p cuyos123 --authenticationDatabase admin --eval "db.getSiblingDB('datengeist_demo').dropDatabase()" 
  
3. Eliminar los Parquet temporales
  
  rm -rf tmp/


---

# ¿Cómo visualizar MONGO?


- Opción 1 — Mongo Express (UI en el browser)
  http://localhost:8081
  - Usuario: admin
  - Contraseña: pass
  
  
- Opción 2 — mongosh (terminal)
  
  docker exec -it mongodb_datengeist mongosh -u admin -p cuyos123 --authenticationDatabase admin

  Una vez dentro:
  use datengeist_demo
  
  // ver colecciones
  show collections
  
  // contar docs de una colección
  db.ventas_completas.countDocuments()
  
  // ver un documento de ejemplo
  db.ventas_completas.findOne()
  
  // ver índices de una colección
  db.ventas_completas.getIndexes()
  

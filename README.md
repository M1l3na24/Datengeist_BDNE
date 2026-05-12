# Datengeist — Proyecto Final BDNE

Proyecto final de la materia **Bases de Datos No Estructuradas**. Implementa un pipeline de datos completo para una heladería ubicada en México (por cuestiones de privacidad no se hace referencia a la empresa) combinando una base de datos relacional (PostgreSQL) con una base de datos documental (MongoDB) y visualización mediante Metabase.

Participantes:
* Ángel N. Pérez
* Ángel J. Zamora
* Isaac Monroy
* Milena F. Rivera
* Valentina A. Cruz
---

## Descripción del proyecto

**Datengeist** simula el sistema de datos de una heladería con 4 años de operación (2021–2024). El proyecto cubre el ciclo completo de datos:

1. **Generación** de datos sintéticos realistas con estacionalidad climática mexicana
2. **Almacenamiento relacional** en PostgreSQL (esquema dimensional)
3. **Pipeline ETL** con arquitectura medallón (Bronce → Plata → Oro)
4. **Almacenamiento documental** en MongoDB (colecciones optimizadas para consultas)
5. **Visualización** mediante un dashboard en Metabase

---

## Arquitectura

```
generador.py
     │
     ▼
PostgreSQL (relacional)        
     │
     ▼  etl.py  (Bronce → Plata → Oro)
     │
     ▼  predictor.py (Logistic Regression)
     │
     ▼
MongoDB (documental)           
     │
     ▼
Metabase Dashboard              
```

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Base de datos relacional | PostgreSQL 15 |
| Base de datos documental | MongoDB |
| ETL / generación de datos | Python 3 · pandas · SQLAlchemy · ScikitLearn |
| Visualización | Metabase v0.48.6 |
| Infraestructura | Docker · Docker Compose |
| Interfaz PostgreSQL | pgAdmin 4 |
| Interfaz MongoDB | Mongo Express |

---

## Estructura del repositorio

```
Datengeist_BDNE/
├── docker-compose.yml        # Infraestructura: 5 servicios Docker
├── datengeist.sql            # Esquema relacional PostgreSQL (6 tablas)
├── crear_colecciones.js      # Colecciones e índices MongoDB (8 colecciones)
├── generador.py              # Generador de datos sintéticos → carga PostgreSQL
├── etl.py                    # Pipeline ETL: PostgreSQL → MongoDB
├── predictor.py              # Análisis predictivo y proyección de ventas
├── Graficas_Tablero.txt      # Consultas utilizadas para llevar información al Dash
├── requirements.txt          # Dependencias Python del proyecto
└── comandos_setup.txt        # Guía de setup paso a paso
```

---

## Modelo de datos

### PostgreSQL — Esquema relacional

| Tabla | Descripción | Registros aprox. |
|---|---|---|
| `Dim_Productos_y_Sabores` | Catálogo de 75 productos (15 sabores × 5 categorías) | 75 |
| `Dim_Clientes_y_Segmentos` | Perfiles de clientes (VIP, Frecuente, Ocasional, Nuevo) | 3,000 |
| `Ventas` | Encabezado de cada ticket de venta | ~1,200,000 |
| `Detalle_ventas` | Líneas de producto por ticket | ~2,600,000 |
| `Operaciones_y_Personal` | Turnos, empleados y costos laborales por día | ~5,800 |
| `Variables_Externas` | Temperatura, precipitación y festivos por fecha | 1,461 |

### MongoDB — Colecciones

| Capa | Colección | Propósito |
|---|---|---|
| Plata | `ventas_completas` | Documento desnormalizado por ticket (cliente + clima + productos) |
| Plata | `catalogo_productos` | Catálogo enriquecido con sabor y rentabilidad derivada |
| Plata | `clientes_perfil` | Perfil de cliente con historial de compras agregado |
| Oro | `kpi_ventas_temporales` | Agregados mensuales y semanales de ventas |
| Oro | `kpi_horarios_afluencia` | Tráfico promedio por hora y día de la semana |
| Oro | `kpi_productos_sabores` | Ranking de productos por ingresos y margen |
| Oro | `kpi_segmentacion` | Ingresos y participación por segmento de cliente |
| Oro | `kpi_metodos_pago` | Distribución de métodos de pago |
|Predictivo| `predicciones_produccion` | Viabilidad de producción a dia inmediato |
|Predictivo| `predicciones_ventas` | Predicción de rentabilidad y tickets |

---

## Dashboard Metabase

El tablero conecta directamente a MongoDB y presenta:

- **4 Indicadores clave (Highlights):** Máximo tickets proyectados, Ventas estimadas para el próximo mes, Tickets semana actual, Total Clientes, Ticket Promedio, Ventas Semana Actual
- **5 Gráficas:** Predicciones de Venta, Plan de Producción por sabor, Predicciones Tickets, Ventas Diarias Estimadas, Segmentación Clientes, Análisis Personal, Rentabilidad, Análisis Temporal, Ventas por Mayoreo, Categoría y Sabor, y Análisis de Tickets.
- **1 Tabla resumen:** Producción sugerida para hoy
- **3 Variables de filtro:** año (2021–2024), segmento de cliente, turno de los empleados

---

## Requisitos previos

- Docker Desktop instalado y corriendo
- Python 3.9+
- Git

---

## Setup

Consulta `comandos_setup.txt` para la guía completa paso a paso. 

---

## Servicios y puertos

| Servicio | URL | Credenciales |
|---|---|---|
| Metabase | http://localhost:3000 | configurar en primer acceso |
| pgAdmin | http://localhost:8080 | correo de angel / cuyos123 |
| Mongo Express | http://localhost:8081 | — |
| PostgreSQL | localhost:5432 | admin / cuyos123 · db: datengeist |
| MongoDB | localhost:27017 | admin / cuyos123 |


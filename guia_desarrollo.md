Perfecto, acá lo tenés como **un único bloque `.md` continuo**, listo para copiar y pegar directo en un archivo:

---

````markdown
# 🌩️ Radar Weather System — Guía de Desarrollo

Sistema de análisis de radares meteorológicos para detección temprana de fenómenos climáticos. San Rafael, Mendoza.

---

## 📋 Requisitos Previos

| Herramienta | Versión | Para qué |
|-------------|---------|----------|
| Python | 3.12+ | Lenguaje base |
| UV | Última | Gestor de paquetes y entornos |
| Docker + Docker Compose | Última | Base de datos PostgreSQL/PostGIS |
| Git | Cualquiera | Control de versiones |

> ⚠️ **Windows:** Docker Desktop incluye Compose.  
> ⚠️ **Linux:** Instalar `docker.io` + `docker-compose-plugin` (o `docker-compose` clásico).  
> ⚠️ **Mac:** Docker Desktop.

---

## 🚀 Inicio Rápido (Flujo Local con UV)

Este es el flujo **diario de desarrollo**. Docker solo corre la base de datos.

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/radar-weather-system.git
cd radar-weather-system
````

### 2. Instalar dependencias con UV

```bash
uv sync
```

> Esto crea automáticamente `.venv/` e instala todo lo definido en `pyproject.toml`.

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env si es necesario (raramente hace falta en local)
```

### 4. Levantar solo la base de datos (Docker)

```bash
docker compose up -d db
```

> Esto descarga PostGIS y lo deja corriendo en `localhost:5432`.

### 5. Verificar que PostgreSQL responde

```bash
docker compose exec db pg_isready -U radar_user -d radar_db
```

> Debe decir: `/var/run/postgresql:5432 - accepting connections`

### 6. Aplicar migraciones de base de datos

```bash
uv run alembic upgrade head
```

### 7. Iniciar la API en modo desarrollo (hot reload)

```bash
uv run fastapi dev app/main.py
```

> La API queda en: [http://localhost:8000](http://localhost:8000)
> Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs)

### 8. Correr tests

```bash
# Todos los tests
uv run pytest -v

# Tests unitarios solo
uv run pytest tests/unit/ -v

# Tests con coverage
uv run pytest --cov=app --cov-report=term-missing

# Watch mode (re-corre al guardar)
uv run pytest -f
```

### 9. Linting y formateo (antes de commitear)

```bash
uv run ruff check .          # Verificar estilo
uv run ruff format .         # Formatear código
uv run mypy app/             # Verificar tipos
```

---

## 🐳 Modo Docker Completo (Validación / Demo)

Usar cuando querés **probar todo el sistema junto** o mostrarle a alguien que no tiene UV instalado.

### Levantar todo (API + DB)

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

> Esto construye la imagen de la app y levanta API + PostGIS juntos.

### Verificar

```bash
curl http://localhost:8000/health
```

### Correr tests dentro del contenedor

```bash
docker compose exec api uv run pytest -v
```

### Apagar todo

```bash
docker compose down -v   # -v borra datos de DB (cuidado)
```

---

## 🔄 Flujo de Trabajo Diario (Resumen)

```bash
# Al empezar a codear
docker compose up -d db          # Si no está corriendo
uv run alembic upgrade head      # Si hay nuevas migraciones
uv run fastapi dev app/main.py   # Levantar API

# En otra terminal (tests, linting, etc.)
uv run pytest -f                 # Tests en watch mode
uv run ruff check .              # Linter

# Al terminar
docker compose down              # Apagar DB
```

---

## 🆘 Troubleshooting

### `permission denied while trying to connect to Docker daemon`

```bash
sudo usermod -aG docker $USER    # Agregar usuario al grupo docker
newgrp docker                     # Aplicar sin cerrar sesión
# O cerrar sesión y volver a entrar
```

### `bash: uv: orden no encontrada`

```bash
# UV no está en el PATH. Recargar shell:
source $HOME/.local/bin/env
# O cerrar y abrir terminal
```

### `connection refused` al conectar a PostgreSQL

```bash
# Verificar que DB está corriendo
docker compose ps
docker compose logs db

# Verificar que .env tiene DATABASE_URL correcto
cat .env | grep DATABASE_URL
```

### Alembic falla con `target_metadata = None`

Es normal al inicio. Cuando crees modelos SQLAlchemy en `app/data/models/`, editá `alembic/env.py` y descomentá la importación de `Base`.

---

## 📁 Estructura Rápida

```
.
├── app/
│   ├── core/           # Config, constantes del PDF, logging
│   ├── processing/     # Subsistema 1: PNG → GeoTIFF
│   ├── business/       # Subsistema 2: GeoTIFF → Análisis (modelo Soria)
│   ├── data/           # SQLAlchemy, repositorios, migraciones
│   └── presentation/   # FastAPI routers y schemas
├── tests/
│   ├── unit/           # Tests aislados (algoritmos, servicios)
│   └── integration/    # Tests con DB real y API
├── docker/             # Dockerfile y entrypoint
├── scripts/            # Utilidades (seed, generadores de test)
└── alembic/            # Migraciones de base de datos
```

---

## 🎯 Principios del Proyecto

| Principio     | Cómo se aplica                                                           |
| ------------- | ------------------------------------------------------------------------ |
| **YAGNI**     | No agregamos TimescaleDB hasta necesitar time-series reales              |
| **DRY**       | Constantes del PDF centralizadas en `app/core/constants.py`              |
| **KISS**      | Pipeline lineal: PNG → GeoTIFF → Análisis. Sin mezclar responsabilidades |
| **SOLID**     | `ProcessingJob` solo trackea estado. `ThreatCalculator` solo calcula A   |
| **TDD**       | Tests unitarios para cada algoritmo. Tests de integración para pipelines |
| **12-Factor** | Config en `.env`. DB stateless. Un codebase, múltiples deploys           |

---

## 📚 Documentación Adicional

* FastAPI: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
* UV: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)
* SQLAlchemy Async: [https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
* Alembic: [https://alembic.sqlalchemy.org/](https://alembic.sqlalchemy.org/)
* PostGIS: [https://postgis.net/documentation/](https://postgis.net/documentation/)

```

---

Si querés dar el siguiente salto, lo podemos :contentReference[oaicite:0]{index=0} (más orientado a CV/portfolio) o en un **doc técnico tipo paper corto** para lo de UNCuyo + gestión de riesgo.
```

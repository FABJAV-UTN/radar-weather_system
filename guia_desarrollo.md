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
```

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

---

## 🗄️ Trabajar con la Base de Datos

### Conectar a PostgreSQL (shell interactiva)

```bash
# Entrar al contenedor de la base de datos
docker exec -it radar-weather_system-db-1 psql -U radar_user -d radar_db
```

> 💡 **Tip:** Si el nombre del contenedor es diferente, verificalo con `docker ps`.

---

### 📊 Consultar registros

```sql
-- Ver cantidad total de imágenes
SELECT COUNT(*) FROM radar_images;

-- Ver últimas 20 imágenes (básico)
SELECT id, filename, image_timestamp, source_type FROM radar_images
ORDER BY image_timestamp DESC LIMIT 20;

-- Ver TODOS los campos de una imagen específica
SELECT * FROM radar_images WHERE id = 1;

-- Paginar resultados (offset/limit)
SELECT id, filename, image_timestamp FROM radar_images
ORDER BY image_timestamp DESC LIMIT 20 OFFSET 0;   -- página 1
SELECT id, filename, image_timestamp FROM radar_images
ORDER BY image_timestamp DESC LIMIT 20 OFFSET 20;  -- página 2

-- Filtrar por ubicación
SELECT * FROM radar_images WHERE location = 'san_rafael';

-- Filtrar por rango de fechas
SELECT * FROM radar_images
WHERE image_timestamp BETWEEN '2026-05-01' AND '2026-05-31';
```

---

### 🗑️ Eliminar registros

```sql
-- Eliminar UNA imagen por ID
DELETE FROM radar_images WHERE id = 1;

-- Eliminar imágenes de una fuente específica
DELETE FROM radar_images WHERE source_type = 'dacc_api';

-- VACIAR TODA la tabla (rápido, reinicia IDs)
TRUNCATE TABLE radar_images RESTART IDENTITY;

-- Vaciar tabla SIN reiniciar IDs (más lento que TRUNCATE)
DELETE FROM radar_images;
```

> ⚠️ **TRUNCATE** es más rápido que `DELETE` porque no borra fila por fila.  
> ⚠️ **RESTART IDENTITY** hace que los IDs vuelvan a empezar desde 1.

---

### 🌐 Ver registros desde el navegador (API REST)

| Acción | URL |
|---|---|
| **Listar imágenes (paginado)** | `http://localhost:8000/api/v1/images?limit=20&offset=0` |
| **Página 2** | `http://localhost:8000/api/v1/images?limit=20&offset=20` |
| **Con filtros** | `http://localhost:8000/api/v1/images?location=san_rafael&date_from=2026-05-01&limit=50&offset=0` |
| **Estadísticas** | `http://localhost:8000/api/v1/images/stats` |
| **Una imagen por ID** | `http://localhost:8000/api/v1/images/1` |
| **Eliminar por ID (curl)** | `curl -X DELETE http://localhost:8000/api/v1/images/1` |

---

## 🧪 Flujo de Desarrollo TDD (Día a Día)

Este proyecto usa **TDD + SDD**. Cada feature nueva sigue este flujo:

### 1. Escribir test primero (RED)

Crear archivo de test en `tests/unit/...` correspondiente. El test debe FALLAR inicialmente porque la implementación no existe.

### 2. Correr test para verificar que falla

```bash
uv run pytest tests/unit/ruta/al/test.py -v
```

### 3. Implementar código mínimo (GREEN)

Crear archivo en `app/...` correspondiente. Hacer que el test pase.

### 4. Correr pipeline de calidad

```bash
uv run pytest -v                    # Tests
uv run ruff check .                 # Linter
uv run ruff format .                # Formato
uv run mypy app/                    # Type checking
```

### 5. Commit

```bash
git add .
git commit -m "feat: descripción de la feature"
```

---

## 🐳 Docker (Validación Completa)

Usar cuando querés validar que todo funciona junto o antes de entregar:

```bash
# Build completo con hot reload
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build

# Tests dentro del contenedor
docker compose exec api uv run pytest -v

# Apagar todo
docker compose down -v
```

---

## 📁 Estructura del Proyecto

```
app/
├── core/                    # Config, constantes, logging
├── presentation/api/v1/     # Endpoints FastAPI
├── processing/              # 🟩 Subsistema 1: PNG → GeoTIFF
│   ├── algorithms/           # png_reader, color_to_dbz, geotiff_writer
│   └── services/             # image_ingestor, georeferencer, etc.
├── business/                # 🟨 Subsistema 2: GeoTIFF → Análisis
│   ├── algorithms/           # zr_marshall_palmer, erosivity, clustering
│   └── services/             # radar_processor, event_detector, report_generator
└── data/                    # 🟥 Capa de Datos: SQLAlchemy + PostGIS
    ├── models/              # Tablas
    └── repositories/        # Acceso a datos

tests/
├── unit/test_processing/     # Tests Subsistema 1
├── unit/test_business/       # Tests Subsistema 2
├── unit/test_presentation/   # Tests API
└── integration/             # Tests end-to-end
```

---

## 🔧 Comandos Útiles

| Comando | Qué hace |
|---------|----------|
| `uv sync` | Instala/actualiza dependencias |
| `uv add <paquete>` | Agrega dependencia |
| `uv add --group dev <paquete>` | Agrega dependencia de dev |
| `uv lock` | Actualiza `uv.lock` |
| `uv run pytest -f` | Tests en watch mode |
| `uv run pytest --cov=app` | Tests con coverage |
| `alembic revision --autogenerate -m "mensaje"` | Crear migración |
| `alembic upgrade head` | Aplicar migraciones |
| `alembic downgrade -1` | Revertir última migración |

---

## 🆘 Troubleshooting

| Problema | Solución |
|----------|----------|
| `permission denied` Docker | `sudo usermod -aG docker $USER` + reiniciar sesión |
| Puerto 5432 ocupado | `docker compose down` o cambiar puerto en `.env` |
| `uv: command not found` | `source $HOME/.local/bin/env` o reiniciar terminal |
| Alembic falla | Verificar `DATABASE_URL` en `.env` y que DB esté corriendo |
| Tests lentos | Usar `pytest -x` (para en primer fallo) o `-k` para filtrar |
| No puedo entrar a psql | Verificar que el contenedor esté corriendo: `docker ps` |
| `TRUNCATE` no funciona | Asegurate de estar dentro de psql (prompt `radar_db=#`) |

---

## 🌐 Variables de Entorno (.env)

| Variable | Default | Para qué |
|----------|---------|----------|
| `DATABASE_URL` | `postgresql+asyncpg://radar_user:radar_pass@localhost:5432/radar_db` | Conexión a PostgreSQL |
| `LOG_LEVEL` | `info` | Nivel de logging |
| `ENVIRONMENT` | `development` | development / staging / production |
| `GEOTIFF_STORAGE_PATH` | `./data/geotiffs` | Dónde guardar GeoTIFFs |

---

## 🔄 CI/CD (GitHub Actions)

Cada `push` a `main` o `develop` corre automáticamente:
- `ruff check`
- `mypy app/`
- `pytest --cov=app`
- Build de Docker

Ver `.github/workflows/ci.yml`
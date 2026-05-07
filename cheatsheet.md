# Radar Weather System — Cheatsheet

## 🧪 Tests

### Con UV (local)

```bash
# Todos los tests
uv run pytest -v

# Solo unitarios
uv run pytest tests/unit/ -v

# Solo integración
uv run pytest tests/integration/ -v

# Un archivo específico
uv run pytest tests/unit/test_processing/test_dacc_scheduler.py -v

# Una clase específica
uv run pytest tests/unit/test_processing/test_dacc_scheduler.py::TestOCRWithRealImage -v

# Watch mode
uv run pytest -f

# Con coverage
uv run pytest --cov=app --cov-report=term-missing
```

### Con Docker

```bash
# Correr todos los tests dentro del contenedor
docker compose exec api uv run pytest -v

# Solo unitarios
docker compose exec api uv run pytest tests/unit/ -v

# Solo integración
docker compose exec api uv run pytest tests/integration/ -v
```

---

## 🗄️ Base de Datos

```bash
# Levantar solo la DB
docker compose up -d db

# Verificar que está lista
docker compose exec db pg_isready -U radar_user -d radar_db

# Aplicar migraciones
uv run alembic upgrade head

# Crear nueva migración
uv run alembic revision --autogenerate -m "descripcion"

# Ver historial de migraciones
uv run alembic history

# Rollback una migración
uv run alembic downgrade -1

# Conectarse a la DB directamente
docker compose exec db psql -U radar_user -d radar_db

# Bajar todo (incluye volumen de datos)
docker compose down -v
```

---

## 🚀 Levantar el proyecto

```bash
# Todo junto
docker compose up --build

# Solo la DB (para desarrollo local con UV)
docker compose up -d db
uv run fastapi dev app/main.py

# Ver logs
docker compose logs -f api
```

---

## 🌐 Endpoints

| Método | Endpoint | Qué hace |
|--------|----------|----------|
| `GET` | `http://localhost:8000/health` | Health check |
| `GET` | `http://localhost:8000/docs` | Swagger UI |
| — | — | — |
| `POST` | `/api/v1/radar/process-local` | Procesa todas las imágenes del banco local (sin OCR, timestamp del filename) |
| `POST` | `/api/v1/radar/process-dacc` | Inicia el loop DACC en background (OCR + crop + -3hs) |
| `POST` | `/api/v1/radar/process-dacc/stop` | Detiene el loop DACC |
| `GET` | `/api/v1/radar/process-dacc/status` | Estado del loop DACC (métricas, contadores) |
| `GET` | `/api/v1/radar/status` | Estado general del sistema (imágenes en DB, espacio en disco) |
| — | — | — |
| `GET` | `/api/v1/images` | Lista imágenes paginadas (params: `limit`, `offset`, `date_from`, `date_to`, `location`) |
| `GET` | `/api/v1/images/stats` | Estadísticas agregadas (total, por fuente, por mes, dBZ máximo) |
| `GET` | `/api/v1/images/{id}` | Obtiene una imagen por ID |
| `GET` | `/api/v1/images/{id}/metadata` | Metadatos de una imagen (dimensiones, dBZ, extent GeoJSON) |
| `DELETE` | `/api/v1/images/{id}` | Elimina imagen de DB y disco |

---

## 🔧 Calidad de código

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app/
```

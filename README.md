# 🌩️ Radar Weather System

Sistema de análisis de radares meteorológicos para detección temprana de fenómenos climáticos. San Rafael, Mendoza.

## Requisitos

- Docker
- Docker Compose

## Ejecutar

```bash
# 1. Clonar
git clone https://github.com/tu-usuario/radar-weather-system.git
cd radar-weather-system

# 2. Configurar variables (opcional, defaults funcionan)
cp .env.example .env

# 3. Levantar todo
docker compose up --build

# 4. Verificar
curl http://localhost:8000/health
```

La API queda en: http://localhost:8000  
Documentación: http://localhost:8000/docs
Frontend: http://localhost:5173


## Apagar

```bash
docker compose down -v
```

---

Para desarrollo, ver [DEVELOPMENT.md](DEVELOPMENT.md)
```

---

## `DEVELOPMENT.md` (Guía para developers)

```markdown
# 🌩️ Radar Weather System — Guía de Desarrollo

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

### 1. Clonar e instalar

```bash
git clone https://github.com/tu-usuario/radar-weather-system.git 
cd radar-weather-system
uv sync
cp .env.example .env
```

### 2. Levantar base de datos

```bash
docker compose up -d db
docker compose exec db pg_isready -U radar_user -d radar_db
```

### 3. Migraciones y arranque

```bash
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

> API en: http://localhost:8000  
> Docs en: http://localhost:8000/docs
> Frontend: http://localhost:5173


---

## 🧪 Flujo TDD (Día a Día)

### 1. Escribir test (RED)

```bash
# Crear test en tests/unit/...
# Debe FALLAR inicialmente
```

### 2. Correr test

```bash
uv run pytest tests/unit/ruta/al/test.py -v
```

### 3. Implementar (GREEN)

```bash
# Crear código en app/...
# Hacer que pase
```

### 4. Calidad

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format .
uv run mypy app/
```

### 5. Commit

```bash
git add .
git commit -m "feat: descripción"
```

---

## 🐳 Docker (Validación Completa)

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
docker compose exec api uv run pytest -v
docker compose down -v
```

---

## 📁 Estructura

```
app/
├── core/                    # Config, constantes
├── presentation/api/v1/     # Endpoints FastAPI
├── processing/              # 🟩 Subsistema 1: PNG → GeoTIFF
│   ├── algorithms/
│   └── services/
├── business/                # 🟨 Subsistema 2: GeoTIFF → Análisis
│   ├── algorithms/
│   └── services/
└── data/                    # 🟥 Capa de Datos
    ├── models/
    └── repositories/

tests/
├── unit/test_processing/
├── unit/test_business/
├── unit/test_presentation/
└── integration/
```

---

## 🔧 Comandos Útiles

| Comando | Qué hace |
|---------|----------|
| `uv sync` | Instala dependencias |
| `uv add <paquete>` | Agrega dependencia |
| `uv add --group dev <paquete>` | Agrega dev dependency |
| `uv lock` | Actualiza lock file |
| `uv run pytest -f` | Tests watch mode |
| `alembic revision --autogenerate -m "msg"` | Crear migración |
| `alembic upgrade head` | Aplicar migraciones |

---

## 🆘 Troubleshooting

| Problema | Solución |
|----------|----------|
| `permission denied` Docker | `sudo usermod -aG docker $USER` + reiniciar sesión |
| Puerto 5432 ocupado | `docker compose down` o cambiar en `.env` |
| `uv: command not found` | `source $HOME/.local/bin/env` |
| Alembic falla | Verificar `DATABASE_URL` y que DB esté corriendo |

reiniciar sesion
```bash
newgrp docker
```

---

## 🌐 Variables de Entorno

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://radar_user:radar_pass@localhost:5432/radar_db` |
| `LOG_LEVEL` | `info` |
| `ENVIRONMENT` | `development` |
| `GEOTIFF_STORAGE_PATH` | `./data/geotiffs` |

---

## 🔄 CI/CD

Cada push a `main` o `develop` corre: `ruff`, `mypy`, `pytest`, Docker build.

Ver `.github/workflows/ci.yml`
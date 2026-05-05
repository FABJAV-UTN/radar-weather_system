#!/bin/bash
set -e

echo "⏳ Esperando PostgreSQL..."
sleep 2

echo "🔄 Ejecutando migraciones..."
uv run alembic upgrade head

echo "✅ Base de datos lista. Iniciando aplicación..."
exec "$@"
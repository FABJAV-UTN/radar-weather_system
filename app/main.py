"""Entry point FastAPI."""

from fastapi import FastAPI

app = FastAPI(
    title="Radar Weather System",
    description="Análisis de radares meteorológicos - San Rafael, Mendoza",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "radar-weather-system"}
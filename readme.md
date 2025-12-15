# Agent CV Analyzer v1.0

Automatización de búsqueda y aplicación a ofertas en LinkedIn usando Comet AI.

## Instalación

```bash
cd c:\Projects\agent_cv_analyzer
pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn main:app --host localhost --port 8080 --reload
```

Luego abrir en navegador: http://localhost:8080

## Requisitos Previos

- Windows
- Python 3.8+
- Comet Browser instalado y abierto
- LinkedIn sesión activa
- 1-2 CVs cargados en perfil de LinkedIn

## Cómo Usar

1. Abrir http://localhost:8080
2. Seleccionar una o más tecnologías
3. Presionar "Buscar en LinkedIn"
4. Esperar a que Comet complete (5-15 minutos)
5. Ver resumen de postulaciones

## Características

- Búsqueda automática en LinkedIn
- Filtros: Remoto, Easy Apply, Últimas 24h, Global
- Selección automática de CV
- Respuesta automática de preguntas
- Ignora empresas bloqueadas (Izertis, Nttdata, PlusATS, Second Windows, Mas Orange, Gosbi, Siigroup, Diverger)
- Almacenamiento de URLs de postulaciones

## Archivos Principales

- `main.py` - Backend FastAPI
- `controlComet.py` - Automatización Comet
- `requirements.txt` - Dependencias
- `templates/` - Interfaz web

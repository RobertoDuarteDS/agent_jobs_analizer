
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import json
import sqlite3
import sys
import asyncio

from controlComet import setPromptLinkedIn, run_prompt
from database import (
    init_db, create_session, is_session_active, 
    close_session, save_application
)

# ===================== Configuración ====================

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

templates = Jinja2Templates(directory="templates")

# ==================== Lifespan (Startup/Shutdown) ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cierre de la aplicación"""
    # STARTUP
    print("✓ Inicializando base de datos...")
    init_db()
    print("✓ Base de datos lista")
    yield
    # SHUTDOWN
    print("✓ Cerrando aplicación...")

app = FastAPI(lifespan=lifespan)

# ===================== Endpoints ========================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("initial_form.html", {"request": request})


# ===================== Endpoints ========================

# Endpoint para consultar el estado de la sesión (si ya terminó)
@app.get("/api/session-status/{session_id}")
async def session_status(session_id: str):
    # Consideramos la sesión completada si ya no está activa
    completed = not is_session_active(session_id)
    return {"completed": completed}

@app.post("/search-linkedin")
async def search_linkedin(request: Request):
    """
    Inicia la búsqueda de ofertas en LinkedIn usando Comet.
    Crea una sesión NUEVA y única para esta búsqueda.
    """
    try:
        data = await request.json()
        technologies = data.get("technologies", [])
        
        if not technologies:
            return JSONResponse(
                status_code=400,
                content={"error": "Debe seleccionar al menos una tecnología"}
            )
        
        # Crear sesión NUEVA y única
        session_id = create_session()
        print(f"✓ Sesión creada: {session_id}")
        
        # Iniciar búsqueda con Comet
        prompt = setPromptLinkedIn(technologies, session_id)
        print(f"✓ Prompt generado para {len(technologies)} tecnologías")

        # Ejecutar automatización de Comet (ventana, teclas, pegado)
        try:
            run_prompt(prompt)
            print("✓ Prompt enviado a Comet correctamente")
        except Exception as e:
            print(f"✗ Error enviando prompt a Comet: {e}")
            # No detenemos el flujo, solo notificamos

        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "redirect": f"/results/{session_id}",
                "technologies": technologies
            }
        )
    
    except Exception as e:
        print(f"✗ Error en search_linkedin: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/results/{session_id}", response_class=HTMLResponse)
async def get_results_page(request: Request, session_id: str):
    """Página de resultados - Solo accesible si sesión está activa"""
    
    # VALIDACIÓN: Verificar que la sesión existe y está activa
    if not is_session_active(session_id):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Sesión no válida o ya completada. Por favor inicia una nueva búsqueda."
        })
    
    return templates.TemplateResponse(
        "resultados.html",
        {
            "request": request,
            "session_id": session_id
        }
    )





@app.get("/historial", response_class=HTMLResponse)
async def historial_page(request: Request):
    """Página de historial de todas las aplicaciones"""
    try:
        conn = sqlite3.connect("aplicaciones.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todas las aplicaciones
        cursor.execute("""
            SELECT url, empresa, titulo, session_id, fecha_hora
            FROM aplicaciones
            ORDER BY fecha_hora DESC
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        apps = [dict(row) for row in rows]
        
        # Obtener total
        cursor.execute("SELECT COUNT(*) FROM aplicaciones")
        total = cursor.fetchone()[0]
        
        conn.close()
        
    except Exception as e:
        print(f"Error en historial_page: {e}")
        apps = []
        total = 0
    
    return templates.TemplateResponse(
        "historial.html",
        {
            "request": request,
            "applications": apps,
            "total": total
        }
    )


@app.post("/api/save-applications-form")
async def save_applications_form(request: Request):
    """
    Recibe datos de aplicaciones desde el formulario
    Formato: URL | Empresa | Título (una por línea)
    Solo acepta si la sesión está activa
    """
    try:
        body = await request.body()
        print(f"DEBUG: Body recibido: {body}")
        
        if not body:
            return JSONResponse(
                status_code=400,
                content={"error": "Body vacío"}
            )
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            print(f"DEBUG: Error al decodificar JSON: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": f"JSON inválido: {str(e)}"}
            )
        
        session_id = data.get('session_id', '')
        applications_data = data.get('applications_data', '')
        
        if not session_id:
            return JSONResponse(
                status_code=400,
                content={"error": "session_id es requerido"}
            )
        
        # VALIDACIÓN CRÍTICA: Verificar que la sesión está activa
        if not is_session_active(session_id):
            return JSONResponse(
                status_code=403,
                content={"error": "Sesión no válida o ya completada. No se pueden guardar datos."}
            )
        
        if not applications_data:
            return JSONResponse(
                status_code=400,
                content={"error": "applications_data es requerido"}
            )
        
        lines = applications_data.strip().split('\n')
        count = 0
        errors = []
        
        print(f"DEBUG: Procesando {len(lines)} líneas")
        
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                print(f"DEBUG: Línea {idx} vacía, saltando")
                continue
            
            if '|' not in line:
                print(f"DEBUG: Línea {idx} sin separador |, saltando")
                errors.append(f"Línea {idx + 1} no tiene separador |")
                continue
            
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 3:
                print(f"DEBUG: Línea {idx} tiene menos de 3 campos: {parts}")
                errors.append(f"Línea {idx + 1} tiene menos de 3 campos")
                continue
            
            url, empresa, titulo = parts[0], parts[1], parts[2]
            print(f"DEBUG: Intentando guardar - URL: {url[:50]}... | Empresa: {empresa} | Título: {titulo}")
            
            if save_application(url, empresa, titulo, session_id):
                count += 1
                print(f"DEBUG: ✓ Aplicación {count} guardada")
            else:
                print(f"DEBUG: ✗ Error guardando aplicación en línea {idx + 1}")
                errors.append(f"Error guardando línea {idx + 1}")
        
        print(f"DEBUG: Total guardadas: {count}/{len([l for l in lines if l.strip()])}")
        
        # SOLO DESACTIVAR LA SESIÓN si se guardaron aplicaciones
        if count > 0:
            close_session(session_id)
            print(f"DEBUG: Sesión {session_id} desactivada después de guardar {count} aplicaciones")
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "message": f"Se guardaron {count} aplicaciones correctamente",
                    "count": count,
                    "errors": errors if errors else None
                }
            )
        else:
            # No se guardó nada, no desactivar la sesión
            print(f"DEBUG: NO se guardó ninguna aplicación. Sesión permanece activa")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "No se pudieron guardar las aplicaciones. Verifica el formato.",
                    "count": 0,
                    "errors": errors
                }
            )
    except Exception as e:
        print(f"DEBUG: Excepción: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )










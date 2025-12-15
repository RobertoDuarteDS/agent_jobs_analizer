# controlComet.py - Automation for LinkedIn job search via Comet
from datetime import date, timedelta, datetime
import pyautogui
import pygetwindow as gw
import time
import psutil
import pyperclip
import win32gui, win32process, win32con, win32api
import ctypes


# Ajusta estos hints si el ejecutable/clase difiere en tu máquina
EXE_HINTS = ("comet", "cometbrowser", "perplexity")        # nombre del .exe (case-insensitive)
CLASS_HINTS = ("Chrome_WidgetWin_1", "Chrome_WidgetWin_0") # típico en Electron/Chromium
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _iter_top_windows():
    hwnds = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetParent(h) == 0:
            hwnds.append(h)
    win32gui.EnumWindows(cb, None)
    return hwnds


def _pid_of_hwnd(hwnd):
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


def _match_process(pid) -> bool:
    try:
        p = psutil.Process(pid)
        name = (p.name() or "").lower()
        exe  = (p.exe() or "").lower()
        return any(h in name or h in exe for h in EXE_HINTS)
    except Exception:
        return False


def _match_class(hwnd) -> bool:
    try:
        cls = win32gui.GetClassName(hwnd) or ""
        return (cls in CLASS_HINTS) or True
    except Exception:
        return False


def _window_area(hwnd) -> int:
    try:
        l,t,r,b = win32gui.GetWindowRect(hwnd)
        return max(0, r-l) * max(0, b-t)
    except Exception:
        return 0


def _attach_foreground(hwnd):
    """
    Trae la ventana al frente incluso si otro hilo tiene el foco.
    Usa AttachThreadInput de user32 y hace Restore + SetForegroundWindow.
    """
    try:
        fg = win32gui.GetForegroundWindow()
    except Exception:
        fg = 0

    tid_active = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
    tid_target = win32process.GetWindowThreadProcessId(hwnd)[0]
    cur_tid    = kernel32.GetCurrentThreadId()

    if tid_active and tid_active != cur_tid:
        user32.AttachThreadInput(cur_tid, tid_active, True)
    if tid_target and tid_target != cur_tid:
        user32.AttachThreadInput(cur_tid, tid_target, True)

    try:
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)

        # Truco "ALT" para sortear restricciones de foreground en Windows
        user32.keybd_event(0x12, 0, 0, 0)  # ALT down
        user32.keybd_event(0x12, 0, 2, 0)  # ALT up

    finally:
        if tid_target and tid_target != cur_tid:
            user32.AttachThreadInput(cur_tid, tid_target, False)
        if tid_active and tid_active != cur_tid:
            user32.AttachThreadInput(cur_tid, tid_active, False)


def _find_comet_hwnd():
    cands = []
    for h in _iter_top_windows():
        pid = _pid_of_hwnd(h)
        if not _match_process(pid):
            continue
        if not _match_class(h):
            continue
        cands.append(h)
    if not cands:
        return None
    return max(cands, key=_window_area)


def _focus_comet_window() -> bool:
    hwnd = _find_comet_hwnd()
    if not hwnd:
        return False

    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    
    # Si está minimizada, restaura
    if show_cmd in (win32con.SW_SHOWMINIMIZED, win32con.SW_MINIMIZE):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
    # Si está maximizada, mantén maximizada
    elif show_cmd == win32con.SW_MAXIMIZE:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.1)
    # Si está normal, mantén normal
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        time.sleep(0.1)

    _attach_foreground(hwnd)
    time.sleep(0.1)
    return True


def _type_prompt_in_omnibox(prompt: str):
    """
    Escribe el prompt en el omnibox de Comet
    Secuencia: nueva pestaña, foco a asistente, escribir, enter
    Optimizado para ejecución rápida
    """
    pyautogui.hotkey("ctrl", "t")      # nueva pestaña
    time.sleep(0.08)
    pyautogui.hotkey("alt", "a")       # foco a asistente
    time.sleep(0.06)
    pyperclip.copy(prompt)
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.1)
    pyautogui.press("enter")


def run_prompt(prompt: str):
    """Lanza la interacción con Comet"""
    ok = _focus_comet_window()
    if not ok:
        raise RuntimeError("No pude enfocar la ventana de Comet. Asegúrate que esté abierto.")
    _type_prompt_in_omnibox(prompt)


def setPromptLinkedIn(technologies, session_id: str = "") -> str:
    """
    Genera el prompt para buscar ofertas en LinkedIn con Comet
    Procesa TODAS las tecnologías secuencialmente en la misma sesión.
    Incluye:
    - Filtros específicos (Remoto, Easy Apply, Últimas 24h)
    - Selección inteligente de CV
    - Respuesta a preguntas de aplicación
    - Filtrado de empresas no deseadas
    - Recolección de URLs de postulaciones
    - Transición automática entre tecnologías
    """
    
    # Asegurar que technologies es una lista
    if isinstance(technologies, str):
        technologies = [technologies]
    
    # Lista de empresas a ignorar (completamente)
    empresas_bloqueadas = [
        "Izertis",
        "Nttdata",
        "PlusATS",
        "Second Windows",
        "Mas Orange",
        "Gosbi",
        "Siigroup",
        "Diverger"
    ]
    
    empresas_str = ", ".join(empresas_bloqueadas)
    technologies_str = ", ".join(technologies)
    technologies_list = "\n".join([f"   {i+1}. {tech}" for i, tech in enumerate(technologies)])
    
    prompt = f"""
AUTOMATIZACIÓN DE APLICACIÓN A OFERTAS EN LINKEDIN

Objetivo: Buscar y aplicar automáticamente a ofertas en LinkedIn
Tecnologías a procesar (SECUENCIALMENTE):
{technologies_list}

Filtros obligatorios:
- Remoto (Remote)
- Aplicación Sencilla (Easy Apply)
- Últimas 24 horas (Past 24 hours)
- País: España (Spain)

EMPRESAS A IGNORAR COMPLETAMENTE:
{empresas_str}
Si una oferta es de estas empresas, SÁLTALA sin aplicar.

FLUJO DE EJECUCIÓN:

CICLO PRINCIPAL - PROCESAR CADA TECNOLOGÍA SECUENCIALMENTE:
=====================================

PARA CADA TECNOLOGÍA EN LA LISTA:

FASE 1: BÚSQUEDA Y FILTRADO
1. Navegar a https://www.linkedin.com/jobs/search/?geoId=105646813
2. En la barra de búsqueda, borra lo anterior e ingresa la SIGUIENTE tecnología
3. Aplicar filtros:
   - Ubicación: "Remote"
   - Facilidad para solicitar: "Easy Apply" (solo mostrar ofertas con este badge)
   - Fecha: "Past 24 hours"
   - País: "Spain" (SOLO España)
4. Ejecutar la búsqueda

FASE 1.5: VERIFICACIÓN DE RESULTADOS
- Revisa si aparecen resultados en la página
- Si NO hay ninguna oferta visible (la página está vacía o dice "No jobs found"):
  * SI ESTA ES LA ÚLTIMA TECNOLOGÍA EN LA LISTA: TERMINA TODO INMEDIATAMENTE
  * SI HAY MÁS TECNOLOGÍAS: Vuelve a FASE 1 con la SIGUIENTE tecnología (sin hacer nada)
- Si hay resultados: Continúa a FASE 2

FASE 2: REVISIÓN Y APLICACIÓN A TODAS LAS OFERTAS
IMPORTANTE: APLICAR A TODAS LAS VACANTES RELACIONADAS A LA TECNOLOGÍA ACTUAL

Para CADA oferta encontrada EN ESTA BÚSQUEDA:
   a) Verificar la empresa (IGNORAR si está en lista de bloqueadas)
   b) Leer el título y descripción rápidamente, si no es relacionada a la tecnología actual, SÁLTALA
   c) Si es relacionada a la tecnología actual: APLICAR haciendo clic en "Easy Apply"
   d) Si NO es relacionada a la tecnología actual: Sáltala, continúa con la siguiente rápidamente

CONTINUAR HASTA:
   - Haber revisado y aplicado a TODAS las ofertas visibles de esta búsqueda
   - NO hayas encontrado más ofertas nuevas después de scrollear

FASE 3: SELECCIÓN DE CV Y RESPUESTA DE PREGUNTAS
Cuando se abra el formulario de aplicación:

   A. SELECCIÓN DE CV:
      IMPORTANTE - ANÁLISIS DE CV BASADO EN LA VACANTE:
      - Lee el título de la oferta y los requisitos principales
      - Identifica la tecnología principal solicitada:
        * Si dice "Java Developer", busca CV con "Java" en el nombre
        * Si dice ".NET Developer", busca CV con "NET" o ".NET" en el nombre
        * Si dice "Python Developer", busca CV con "Python" en el nombre
      
      PASO 1 - BÚSQUEDA EN LISTA INICIAL:
      - En la lista de CVs disponibles inicial:
        * Busca el que contenga la palabra clave de la tecnología en su nombre de archivo
        * Selecciona ese CV específico (no el primero o más reciente)
        * Si no hay coincidencia exacta, selecciona el más general/completo. Pero siempre verifica todos los curriculums disponibles.
        * Si encuentra el CV: Ir a PASO 3
      
      PASO 2 - EXPANDIR LISTA SI NO ENCONTRASTE:
      - Si NO encontraste el CV en la lista inicial:
        * Busca el botón que dice "Mostrar X curriculums más" o "Show more CVs"
        * Haz clic en ese botón para expandir la lista
        * Una nueva lista más grande se desplegará
        * Busca nuevamente el CV con la palabra clave de la tecnología
        * Cuando lo encuentres, continúa a PASO 3
      
      PASO 3 - SELECCIONAR EL CV CORRECTO:
      - IMPORTANTE - BOTÓN CORRECTO:
        * Cada CV en la lista tiene DOS BOTONES: uno para DESCARGAR y otro para SELECCIONAR
        * NO hagas clic en el botón de DESCARGAR (Download)
        * Haz clic en el botón de SELECCIONAR (Select / Choose / Use this CV)
        * El botón de seleccionar generalmente está a la derecha o tiene un icono de check/confirmación
      - Confirma la selección del CV apropiado

   B. RESPUESTA DE PREGUNTAS:
      Si la plaza hace preguntas adicionales:
      - Lee cada pregunta cuidadosamente
      - Si pregunta sobre años de experiencia:
        * Si pide N años, responde: N+1 o N+2 años (varía ligeramente)
        * Ejemplo: Si pide 4 años en Java, responde "5 años" o "6 años"
      - Si pregunta sobre skills específicos: confirma que tienes el skill
      - Si pregunta sobre disponibilidad: responde "Disponible inmediatamente"
      - Si pregunta sobre salario: responde "Flexible/Negotiable" o un rango realista
      - Responde de forma coherente con la oferta y tu CV
      - Mantén respuestas breves y profesionales

   C. ENVIO DE APLICACIÓN:
      - Una vez respondidas todas las preguntas (si las hay)
      - Presiona el botón "Submit" o "Send Application"
      - Espera confirmación de que la aplicación se envió

FASE 4: REGISTRO Y RECOPILACIÓN
- Para cada aplicación exitosa, registra:
  * URL de la oferta
  * Nombre de la empresa
  * Título del puesto
  * Estado: "Aplicado"

FASE 5: DETECCIÓN DE FIN DE TECNOLOGÍA Y CAMBIO A LA SIGUIENTE
- Continúa scrolleando hacia abajo en los resultados de búsqueda
- Si NO hay más ofertas nuevas después de scrollear (se repiten las que ya viste):
  * Has completado TODAS las ofertas para esta tecnología
  * Registra el conteo total de aplicaciones para esta tecnología
  * SI HAY MÁS TECNOLOGÍAS EN LA LISTA: Vuelve a FASE 1 con la SIGUIENTE tecnología (en la misma ventana)
  * SI NO HAY MÁS TECNOLOGÍAS: Ve a RECOLECCIÓN FINAL
- Si hay más ofertas: Vuelve a FASE 2

RECOLECCIÓN FINAL (AL COMPLETAR TODAS LAS TECNOLOGÍAS):
Al terminar la última tecnología:

1. Abre la página de resultados:
   - Ve a: http://127.0.0.1:8080/results/{session_id}
   - Espera a que cargue completamente la página

2. IMPORTANTE - INGRESAR DATOS EN EL FORMULARIO VISIBLE:
   - Encontrarás un área de texto grande (textarea) etiquetada como "Aplicaciones (una por línea):"
   - Haz clic en ese textarea para enfocarlo
   - Escribe cada aplicación en el siguiente formato (una por línea):
   
   Formato EXACTO: URL | Empresa | Título del Puesto
   
   Ejemplo completo (copia este formato exacto):
   https://linkedin.com/jobs/123456 | Acme Corp | Python Developer
   https://linkedin.com/jobs/789012 | TechCo Inc | Senior Java Developer
   https://linkedin.com/jobs/345678 | DataSys | .NET Developer

3. DESPUÉS DE ESCRIBIR TODOS LOS DATOS:
   - Localiza el botón azul que dice "Guardar Aplicaciones" (tiene un icono de disco)
   - Haz clic en ese botón
   - Espera a que se confirme (verás un mensaje de éxito)
   - Los datos se guardarán automáticamente en la base de datos

4. DETALLES CRÍTICOS:
   - NUNCA incluyas líneas vacías entre aplicaciones
   - Asegúrate de usar el separador | (pipe/barra vertical) entre URL, Empresa y Título
   - La URL debe ser la URL COMPLETA de la oferta en LinkedIn
   - El nombre de la empresa y título deben ser exactos
   - Si una aplicación tiene caracteres especiales, mantenlos
   - Una aplicación por línea, sin excepciones
   
5. VALIDACIÓN FINAL:
   - Podrás ver el historial de todas tus aplicaciones en: http://127.0.0.1:8080/historial

NOTAS IMPORTANTES:
- BÚSQUEDA LIMITADA A ESPAÑA ÚNICAMENTE
- Si no hay ofertas en Tech 1 o 2: Pasa a la siguiente sin hacer nada
- Si no hay ofertas en la ÚLTIMA tecnología: TERMINA TODO EL PROCESO
- NUNCA apliques a empresas en la lista de bloqueadas
- Si una oferta no tiene Easy Apply badge, sáltala
- Si hay error al aplicar, continúa con la siguiente
- Las respuestas a preguntas deben ser congruentes con la plaza
- Si Comet no logra aplicar a una oferta, continúa sin detener
- Registra el LINK EXACTO de cada oferta aplicada (sin acortar)
- Mantén las aplicaciones progresivas sin cerrar sesión
- NO CIERRES NI ABRAS PESTAÑAS - Todo debe ser en la MISMA sesión
- El session_id es: {session_id}
- IMPORTANTE: Procesa tecnologías SIN pausas entre ellas (cambio automático)
- VELOCIDAD: Trabaja lo más rápido posible, no esperes innecesariamente
- NO hagas pausas largas entre acciones, sé ágil en las interacciones

VALIDACIÓN:
- Asegúrate de que las aplicaciones se enviaron correctamente
- Verifica que recibas confirmación de cada aplicación
- Si la página no carga, reintenta
- Proporciona el conteo total de aplicaciones enviadas (por cada tecnología)
- Confirma cuando completes TODAS las tecnologías: {technologies_str}
"""
    return prompt


def debug():
    """Retorna información de debug sobre ventanas disponibles"""
    titles = [t for t in gw.getAllTitles() if (t or "").strip()]
    return {"count": len(titles), "titles": titles[:200]}

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

FASE 2: REVISIÓN DE TODAS LAS OFERTAS
Revisa maximo 5 ofertas de cada tecnología, debido a la limitación de tiempo.

Para CADA oferta encontrada EN ESTA BÚSQUEDA:
   a) Verificar la empresa (IGNORAR si está en lista de bloqueadas)
   b) Leer el título y descripción rápidamente, si no es relacionada a la tecnología actual, SÁLTALA
   c) Si es relacionada a la tecnología actual: Ingresa y recopila información de la oferta de la siguiente manera:
      *Título
      *Empresa
      *Descripción completa
      *Requisitos
      *“Nice to have”
      *URL de la oferta
   d) Si NO es relacionada a la tecnología actual: Sáltala, continúa con la siguiente rápidamente

CONTINUAR HASTA:
   - Haber revisado y recopilado TODAS las ofertas visibles de esta búsqueda
   - NO hayas encontrado más ofertas nuevas después de scrollear
   - Haber registrado TODAS las ofertas relevantes para esta tecnología (si son varias tecnologías, repetir el proceso para cada tecnología)

FASE 3: SELECCIÓN DE CV
Luego de haber recopilado la informacion de TODAS las ofertas relevantes de las tecnologias, se procede con lo siguiente:

   A. COMPARACIÓN DE PLANTILLA CV:

      PASO 1 - MODIFICACION DE CVs:
      - Ve a https://www.docs.google.com
      - Busca en la lista de documentos, el CV que contiene la palabra clave de la primera tecnología de la lista
      - Abre el documento.

      PASO 2 - COMPARACIÓN DE CVs:
      - Lee el documento, analizalo y comparalo con ofertas que recopilaste en la busqueda.
      - Si la oferta requiere habilidades o experiencia que el CV no tiene, crear una copia del CV en Archivo > Hacer una copia. La copia debe tener en el titulo: "CV_tecnologia_oferta", tecnologia es la tecnologia que se busca y la oferta es la oferta que se aplica.
      - Si al CV le hace falta alguna habilidad o experiencia que la oferta requiere, agrega esa habilidad en el nuevo archivo y en alguna parte del CV, procurando que se vea bonito y ordenado.
      - Si el CV ya cumple con los requisitos de la oferta, no es necesario hacer una copia, se puede usar el mismo CV.
      - Descarga el CV modificado en formato PDF. (Archivo > Descargar > Documento PDF (.pdf))
      - Realiza este proceso para cada oferta de la primera tecnologia.

      IMPORTANTE: 
        - Repite el PASO 1 y PASO 2 para cada tecnologia en la lista, asegurandote de crear copias del CV para cada oferta que lo requiera.
        - Memoriza los nombres de los archivos de CVS que has creado.

 

NOTAS IMPORTANTES:
- Si el proceso es largo, no importa, no debes parar el proceso, ni resumirlo, debes seguir el flujo hasta terminar y llegar al final de la tarea.
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
- Si la página no carga, reintenta
- Proporciona el conteo total de aplicaciones enviadas (por cada tecnología)
- Confirma cuando completes TODAS las tecnologías: {technologies_str}
"""
    return prompt


def debug():
    """Retorna información de debug sobre ventanas disponibles"""
    titles = [t for t in gw.getAllTitles() if (t or "").strip()]
    return {"count": len(titles), "titles": titles[:200]}

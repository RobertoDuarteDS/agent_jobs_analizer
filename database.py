import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import uuid

DB_PATH = "aplicaciones.db"

def init_db():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    print("DEBUG DB: Inicializando base de datos...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            session_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'activa',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP
        )
    """)
    print("DEBUG DB: Tabla sesiones OK")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aplicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            empresa TEXT NOT NULL,
            titulo TEXT NOT NULL,
            session_id TEXT NOT NULL,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("DEBUG DB: Tabla aplicaciones OK")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aplicaciones_vacantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT NOT NULL,
            hora_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("DEBUG DB: Tabla aplicaciones_vacantes OK")
    
    conn.commit()
    conn.close()
    print("DEBUG DB: Base de datos inicializada correctamente")


def insertar_aplicacion_vacante(nombre_archivo: str):
    """Guarda el nombre de un CV generado en la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO aplicaciones_vacantes (nombre_archivo) VALUES (?)",
        (nombre_archivo,)
    )
    conn.commit()
    conn.close()


def create_session() -> str:
    """Crea una nueva sesión única"""
    session_id = f"linkedin_{uuid.uuid4().hex[:8]}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sesiones (session_id, status)
        VALUES (?, 'activa')
    """, (session_id,))
    conn.commit()
    conn.close()
    
    print(f"DEBUG: Sesión creada: {session_id}")
    return session_id


def get_session(session_id: str) -> Optional[Dict]:
    """Obtiene información de una sesión"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sesiones WHERE session_id = ?", (session_id,))
        session = cursor.fetchone()
        conn.close()
        return dict(session) if session else None
    except Exception as e:
        print(f"Error getting session: {e}")
        return None


def is_session_active(session_id: str) -> bool:
    """Verifica si la sesión está activa"""
    session = get_session(session_id)
    return session is not None and session.get('status') == 'activa'


def close_session(session_id: str) -> bool:
    """Desactiva la sesión después de guardar aplicaciones"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sesiones 
            SET status = 'completada', fecha_cierre = CURRENT_TIMESTAMP
            WHERE session_id = ?
        """, (session_id,))
        conn.commit()
        conn.close()
        print(f"DEBUG: Sesión {session_id} desactivada")
        return True
    except Exception as e:
        print(f"Error closing session: {e}")
        return False


def save_application(url: str, empresa: str, titulo: str, session_id: str) -> bool:
    """Guarda una aplicación en la BD"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print(f"DEBUG DB: Guardando - Session: {session_id}, Empresa: {empresa}, Título: {titulo[:30]}...")
        
        cursor.execute("""
            INSERT INTO aplicaciones (url, empresa, titulo, session_id)
            VALUES (?, ?, ?, ?)
        """, (url, empresa, titulo, session_id))
        
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        print(f"DEBUG DB: ✓ Inserción exitosa. Filas afectadas: {rows_affected}")
        return True
    except sqlite3.IntegrityError as e:
        print(f"DEBUG DB: ✗ Error de integridad: {e}")
        return False
    except sqlite3.OperationalError as e:
        print(f"DEBUG DB: ✗ Error operacional (tabla no existe?): {e}")
        print(f"DEBUG DB: Intentando recrear tabla...")
        try:
            init_db()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO aplicaciones (url, empresa, titulo, session_id)
                VALUES (?, ?, ?, ?)
            """, (url, empresa, titulo, session_id))
            conn.commit()
            conn.close()
            print(f"DEBUG DB: ✓ Reintentos exitoso después de recrear tabla")
            return True
        except Exception as retry_error:
            print(f"DEBUG DB: ✗ Error en reintento: {retry_error}")
            return False
    except Exception as e:
        print(f"DEBUG DB: ✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_applications_batch(applications: List[Dict], session_id: str) -> int:
    """Guarda múltiples aplicaciones en la BD"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        count = 0
        for app in applications:
            cursor.execute("""
                INSERT INTO aplicaciones (url, empresa, titulo, session_id)
                VALUES (?, ?, ?, ?)
            """, (
                app.get('url'),
                app.get('empresa'),
                app.get('titulo'),
                session_id
            ))
            count += 1
        
        conn.commit()
        conn.close()
        return count
    except Exception as e:
        print(f"Error saving applications batch: {e}")
        return 0

def get_applications(limit: int = 100) -> List[Dict]:
    """Obtiene las últimas aplicaciones"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, empresa, titulo, session_id, fecha_hora
            FROM aplicaciones
            ORDER BY fecha_hora DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting applications: {e}")
        return []

def get_applications_count() -> int:
    """Obtiene el total de aplicaciones guardadas"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM aplicaciones")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    except Exception as e:
        print(f"Error al contar aplicaciones: {e}")
        return 0



def get_applications_by_session(session_id: str) -> List[Dict]:
    """Obtiene aplicaciones de una sesión específica"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, empresa, titulo, session_id, fecha_hora
            FROM aplicaciones
            WHERE session_id = ?
            ORDER BY fecha_hora DESC
        """, (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting applications by session: {e}")
        return []

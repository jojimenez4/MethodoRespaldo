"""
Script para limpiar logs antiguos y archivos de debug.
Mantiene solo los logs productivos necesarios.
"""

import os
import glob
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_debug_logs():
    """Elimina archivos de logs de debug y mantiene solo logs productivos."""
    
    # Directorio base de la aplicación
    app_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = app_dir / "logs"
    
    # Crear directorio de logs si no existe
    logs_dir.mkdir(exist_ok=True)
    
    # Archivos a mantener (logs productivos)
    keep_files = {
        'app.log',
        'service.log'
    }
    
    # Patrones de archivos a eliminar
    debug_patterns = [
        '*.debug',
        '*.tmp',
        '*.log.*',  # logs rotados antiguos
        'debug_*.log',
        'test_*.log',
        '*.bak'
    ]
    
    files_removed = 0
    
    try:
        # Limpiar archivos de debug
        for pattern in debug_patterns:
            for file_path in glob.glob(str(logs_dir / pattern)):
                try:
                    os.remove(file_path)
                    files_removed += 1
                    logger.info(f"Eliminado: {file_path}")
                except Exception as e:
                    logger.error(f"Error al eliminar {file_path}: {e}")
        
        # Limpiar logs antiguos (mantener solo los últimos 30 días)
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for log_file in logs_dir.glob("*.log"):
            if log_file.name in keep_files:
                # Para logs productivos, verificar tamaño
                if log_file.stat().st_size > 50 * 1024 * 1024:  # 50MB
                    # Rotar log grande
                    backup_name = f"{log_file.stem}_{datetime.now().strftime('%Y%m%d')}.bak"
                    backup_path = logs_dir / backup_name
                    
                    # Mover contenido a backup
                    log_file.rename(backup_path)
                    
                    # Crear nuevo archivo de log
                    log_file.touch()
                    
                    logger.info(f"Log rotado: {log_file} -> {backup_path}")
            else:
                # Eliminar logs que no están en la lista de mantener
                try:
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        log_file.unlink()
                        files_removed += 1
                        logger.info(f"Log antiguo eliminado: {log_file}")
                except Exception as e:
                    logger.error(f"Error al procesar {log_file}: {e}")
        
        # Limpiar archivos temporales en el directorio principal
        temp_patterns = [
            '*.tmp',
            '*.temp',
            'test_*',
            '*.corrupto'
        ]
        
        for pattern in temp_patterns:
            for file_path in glob.glob(str(app_dir / pattern)):
                try:
                    os.remove(file_path)
                    files_removed += 1
                    logger.info(f"Archivo temporal eliminado: {file_path}")
                except Exception as e:
                    logger.error(f"Error al eliminar {file_path}: {e}")
        
        logger.info(f"Limpieza completada. {files_removed} archivos eliminados.")
        
    except Exception as e:
        logger.error(f"Error durante la limpieza: {e}")

if __name__ == "__main__":
    clean_debug_logs()

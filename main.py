import logging
import sys
import argparse
import os
import time
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Determinar si la aplicación está empaquetada con PyInstaller
def is_bundled():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# Obtener la ruta base de la aplicación (funciona con PyInstaller)
def get_app_path():
    if is_bundled():
        # Si está empaquetada, usar la ruta del ejecutable
        return os.path.dirname(sys.executable)
    else:
        # Si no está empaquetada, usar la ruta del script
        return os.path.dirname(os.path.abspath(__file__))

# Establecer el directorio base de la aplicación
APP_DIR = get_app_path()
os.chdir(APP_DIR)  # Cambiar al directorio de la aplicación

# Configuración de logging
LOG_FILE = os.path.join(APP_DIR, "logs", "app.log")
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Configuración de archivo específico para modo servicio
SERVICE_LOG_FILE = os.path.join(APP_DIR, "logs", "service.log")

# Configurar logger
logger = logging.getLogger("BackupSystem")
logger.setLevel(logging.INFO)

def setup_logging():
    """Configura el sistema de logging."""
    # Asegurar que el directorio de logs existe
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    # Configurar manejadores de logs
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    
    # Añadir manejador de consola (solo para modo interactivo, no para servicio)
    if not is_service_mode():
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console_handler)
    
    logger.info(f"Iniciando aplicación MethodoRespaldo desde: {APP_DIR}")
    if is_bundled():
        logger.info("Ejecutando como aplicación empaquetada")
    else:
        logger.info("Ejecutando como script Python")

def is_service_mode():
    """Determina si la aplicación se está ejecutando en modo servicio."""
    return "--service" in sys.argv

def ensure_app_directories():
    """Crea todos los directorios necesarios para la aplicación."""
    directories = [
        os.path.join(APP_DIR, "logs"),
        os.path.join(APP_DIR, "temp"),
        os.path.join(APP_DIR, "assets")
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Directorio asegurado: {directory}")
        except Exception as e:
            logger.error(f"Error al crear directorio {directory}: {e}")

# Configuración inicial de logging básico para capturar errores tempranos
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        filename=LOG_FILE,
        filemode='a'
    )
except Exception as e:
    # Si no podemos configurar logging, al menos mostrar error en consola
    print(f"Error al configurar logging inicial: {e}")

# Ahora importamos el resto de módulos
try:
    # Importar después de configurar rutas y logging inicial
    from config_manager import ConfigManager
    from backup_manager import BackupManager
    from views import create_login_interface, create_system_tray_icon, AppState
except Exception as e:
    logger.critical(f"Error al importar módulos: {e}", exc_info=True)
    print(f"Error crítico al importar módulos: {e}")
    sys.exit(1)

def parse_arguments():
    """Procesa los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Sistema de respaldo de bases de datos")
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Activa el modo debug con más información en logs'
    )
    parser.add_argument(
        '--backup-now', 
        action='store_true',
        help='Ejecuta un respaldo inmediato usando la configuración guardada'
    )
    parser.add_argument(
        '--service', 
        action='store_true',
        help='Ejecuta la aplicación como servicio Windows'
    )
    return parser.parse_args()

def start_scheduled_backups():
    """Inicia la ejecución de respaldos programados."""
    try:
        config_manager = ConfigManager()
        program_state = config_manager.get_program_state()
        
        # Verificar si hay respaldo programado
        scheduled = program_state.get("scheduled", False)
        logger.info(f"Estado de programación al iniciar: {scheduled}")
        
        # Obtener parámetros de programación
        backup_hours = program_state.get("backup_hours", 4)
        backup_minutes = program_state.get("backup_minutes", 0)
        backup_dir = program_state.get("backup_dir")
        
        # Verificar que hay un directorio de respaldo (esto es lo único realmente necesario)
        if not backup_dir:
            logger.warning("No hay directorio de respaldo configurado")
            # Usar directorio predeterminado
            backup_dir = os.path.join(APP_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Usando directorio de respaldo predeterminado: {backup_dir}")
            # Actualizar estado
            config_manager.update_program_state(backup_dir=backup_dir)
        
        # Asegurar que el directorio existe
        try:
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Directorio de respaldo verificado: {backup_dir}")
        except Exception as e:
            logger.error(f"Error al verificar directorio de respaldo: {e}")
            # Intentar usar un directorio alternativo
            backup_dir = os.path.join(APP_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Usando directorio de respaldo alternativo: {backup_dir}")
            config_manager.update_program_state(backup_dir=backup_dir)
        
        # Configurar programador con comprobación previa
        backup_manager = BackupManager()
        
        # Función que verifica condiciones antes de ejecutar respaldo
        def execute_backup_safely():
            # Recargar configuración cada vez
            current_state = config_manager.get_program_state()
            current_server_data = config_manager.get_server_data()
            
            # Verificar si hay datos suficientes para el respaldo
            if not current_server_data.get("password") or not current_server_data.get("client"):
                logger.warning("Datos de servidor insuficientes para ejecutar respaldo")
                return False
            
            # Ejecutar respaldo
            try:
                # Hacer copia local de los parámetros importantes para evitar referencias perdidas
                password = current_server_data.get("password", "")
                backup_directory = current_state.get("backup_dir", backup_dir)
                client_name = current_server_data.get("client", "Cliente")
                amount_value = current_state.get("amount", 5)
                server_data_copy = current_server_data.copy()
                
                # Registrar inicio de respaldo
                logger.info(f"Iniciando respaldo programado para {client_name} en {backup_directory}")
                
                # Actualizar estado antes de ejecutar
                config_manager.update_program_state(
                    running=True,
                    status="in_progress",
                    timestamp=datetime.datetime.now().isoformat()
                )
                
                # Ejecutar respaldo
                result = backup_manager.backup_mysql_database(
                    password,
                    backup_directory,
                    client_name,
                    amount_value,
                    server_data_copy
                )
                
                # Actualizar estado al finalizar
                if result:
                    config_manager.update_program_state(
                        status="completed",
                        running=True
                    )
                    logger.info(f"Respaldo programado completado exitosamente")
                else:
                    config_manager.update_program_state(
                        status="error",
                        running=True
                    )
                    logger.error("Respaldo programado falló")
                
                # Forzar que todos los campos estén presentes
                config_manager.force_save_all()
                
                return result
            except Exception as e:
                logger.error(f"Error al ejecutar respaldo programado: {e}", exc_info=True)
                config_manager.update_program_state(
                    status="error",
                    running=True
                )
                config_manager.force_save_all()
                return False
        
        # Programar respaldo con la función segura
        if scheduled:
            backup_manager.scheduler.schedule_backup(
                backup_hours,
                backup_minutes,
                execute_backup_safely
            )
            logger.info(f"Respaldos programados iniciados: cada {backup_hours}h:{backup_minutes}m")
        else:
            # Si no hay programación activa, configurar una predeterminada
            logger.info("No hay respaldo programado configurado, estableciendo respaldo cada 4 horas")
            config_manager.set_backup_schedule(4, 0, True)
            
            # Actualizar estado
            config_manager.force_save_all()
            
            # Programar con valores predeterminados
            backup_manager.scheduler.schedule_backup(4, 0, execute_backup_safely)
            logger.info("Respaldos programados iniciados con configuración predeterminada: cada 4h:0m")
        
        return True
    except Exception as e:
        logger.error(f"Error al iniciar respaldos programados: {e}", exc_info=True)
        return False

def run_as_service():
    """Ejecuta la aplicación en modo servicio."""
    logger.info("Iniciando aplicación en modo servicio")
    
    # Configurar logger específico para modo servicio
    try:
        service_handler = logging.FileHandler(SERVICE_LOG_FILE, encoding='utf-8')
        service_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(service_handler)
        
        # Remover manejador de consola en modo servicio
        for handler in list(logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
    except Exception as e:
        # No podemos usar logger aquí si falló la configuración
        print(f"Error al configurar logs de servicio: {e}")
    
    try:
        # Iniciar programador de respaldos
        success = start_scheduled_backups()
        if success:
            logger.info("Servicio de respaldo iniciado correctamente")
            
            # Mantener el programa en ejecución
            while True:
                time.sleep(60)  # Dormir para no consumir CPU
                
        else:
            logger.error("No se pudo iniciar el servicio de respaldo")
            return 1
    except KeyboardInterrupt:
        logger.info("Servicio detenido por el usuario")
        return 0
    except Exception as e:
        logger.critical(f"Error fatal en el servicio: {e}", exc_info=True)
        return 1

def run_backup_immediate():
    """Ejecuta un respaldo inmediato usando la configuración guardada."""
    logger.info("Ejecutando respaldo inmediato...")
    
    try:
        config_manager = ConfigManager()
        program_state = config_manager.get_program_state()
        server_data = config_manager.get_server_data()
        
        if program_state.get("backup_dir") and server_data.get("password"):
            try:
                # Verificar que el directorio de respaldo existe
                backup_dir = program_state.get("backup_dir")
                os.makedirs(backup_dir, exist_ok=True)
                
                backup_manager = BackupManager()
                backup_manager.backup_mysql_database(
                    server_data["password"],
                    program_state["backup_dir"],
                    server_data.get("client", "Cliente"),
                    program_state.get("amount", 5),
                    server_data
                )
                logger.info("Respaldo inmediato completado")
                return 0
            except Exception as e:
                logger.error(f"Error en respaldo inmediato: {e}", exc_info=True)
                return 1
        else:
            logger.error("No hay configuración para respaldo inmediato")
            return 1
    except Exception as e:
        logger.error(f"Error general en run_backup_immediate: {e}", exc_info=True)
        return 1

def initialize_app():
    """Inicializa la aplicación y maneja cualquier error de inicio."""
    try:
        # Configurar logging adecuado
        setup_logging()
        
        # Asegurar que los directorios necesarios existan
        ensure_app_directories()
        
        # Procesar argumentos
        args = parse_arguments()
        
        # Configurar nivel de log según argumentos
        if args.debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Modo debug activado")
        
        # Si se solicita ejecución como servicio
        if args.service or is_service_mode():
            return run_as_service()
        
        # Si se solicita respaldo inmediato
        if args.backup_now:
            return run_backup_immediate()
        
        # Iniciar la interfaz de login (modo normal)
        create_login_interface()
        return 0
        
    except Exception as e:
        try:
            logger.critical(f"Error fatal al iniciar la aplicación: {e}", exc_info=True)
        except:
            print(f"Error crítico: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = initialize_app()
        sys.exit(exit_code)
    except Exception as e:
        try:
            logger.critical(f"Error no capturado: {e}", exc_info=True)
        except:
            print(f"Error crítico no manejado: {e}")
        sys.exit(1)
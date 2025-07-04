import logging
import sys
import argparse
import os
import time
import datetime
import schedule
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
    # Si no podemos configurar logging, usar logger básico
    logger.critical(f"Error al configurar logging inicial: {e}")

# Ahora importamos el resto de módulos
try:
    # Importar después de configurar rutas y logging inicial
    from config_manager import ConfigManager
    from backup_manager import BackupManager
    from views import create_login_interface, create_system_tray_icon, AppState
except Exception as e:
    logger.critical(f"Error al importar módulos: {e}", exc_info=True)
    sys.exit(1)

def parse_arguments():
    """Procesa los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Sistema de respaldo de bases de datos")
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
        
        # Asegurar que el directorio existe con permisos adecuados
        try:
            # Probar crear el directorio con permisos explícitos
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Directorio de respaldo verificado: {backup_dir}")
            
            # Verificar permisos intentando escribir un archivo temporal
            check_file = os.path.join(backup_dir, "check_write.tmp")
            try:
                with open(check_file, 'w') as f:
                    f.write("check")
                os.remove(check_file)
                logger.info(f"Permiso de escritura en directorio verificado")
            except Exception as write_error:
                logger.error(f"Error de permisos de escritura en {backup_dir}: {write_error}")
                # Intentar usar un directorio alternativo
                backup_dir = os.path.join(APP_DIR, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                logger.info(f"Cambiando a directorio de respaldo alternativo: {backup_dir}")
                config_manager.update_program_state(backup_dir=backup_dir)
        except Exception as e:
            logger.error(f"Error al verificar directorio de respaldo: {e}")
            # Intentar usar un directorio alternativo
            backup_dir = os.path.join(APP_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Usando directorio de respaldo alternativo: {backup_dir}")
            config_manager.update_program_state(backup_dir=backup_dir)
        
        # Verificar datos del servidor
        server_data = config_manager.get_server_data()
        if not server_data:
            logger.error("No hay datos de servidor configurados")
            return False
            
        if not server_data.get("password"):
            logger.error("Contraseña de servidor no configurada")
            return False
            
        if not server_data.get("client"):
            logger.warning("Nombre de cliente no configurado")
            server_data["client"] = "Cliente_Predeterminado"
            config_manager.update_server_data(client="Cliente_Predeterminado")
        
        # Configurar programador con comprobación previa
        backup_manager = BackupManager()
        
        # Función que verifica condiciones antes de ejecutar respaldo
        def execute_backup_safely():
            # Recargar configuración cada vez
            try:
                current_state = config_manager.get_program_state()
                current_server_data = config_manager.get_server_data()
                
                # Verificar si hay datos suficientes para el respaldo
                if not current_server_data.get("password") or not current_server_data.get("client"):
                    logger.warning("Datos de servidor insuficientes para ejecutar respaldo")
                    return False
                
                # Hacer copia local de los parámetros importantes para evitar referencias perdidas
                try:
                    password = current_server_data.get("password", "")
                    backup_directory = current_state.get("backup_dir", backup_dir)
                    client_name = current_server_data.get("client", "Cliente")
                    amount_value = current_state.get("amount", 5)
                    server_data_copy = current_server_data.copy()
                    
                    # Verificar que el directorio existe y se puede escribir
                    try:
                        os.makedirs(backup_directory, exist_ok=True)
                        check_file = os.path.join(backup_directory, "check_write.tmp")
                        with open(check_file, 'w') as f:
                            f.write("check")
                        if os.path.exists(check_file):
                            os.remove(check_file)
                        logger.info(f"Directorio de respaldo verificado con permisos: {backup_directory}")
                    except Exception as dir_error:
                        logger.error(f"Error de permisos en directorio de respaldo: {dir_error}")
                        return False
                    
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
                except Exception as exec_error:
                    logger.error(f"Error durante la ejecución del respaldo: {exec_error}", exc_info=True)
                    config_manager.update_program_state(
                        status="error", 
                        running=True
                    )
                    return False
            except Exception as e:
                logger.error(f"Error al preparar respaldo programado: {e}", exc_info=True)
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
        
        # Verificar que el scheduler está en funcionamiento
        if not backup_manager.scheduler.is_scheduled():
            logger.error("El scheduler no se inició correctamente")
            return False
            
        logger.info("Scheduler iniciado correctamente")
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
                
        logger.info("Configuración de logging en modo servicio completada")
    except Exception as e:
        # No podemos usar logger aquí si falló la configuración
        pass
    
    # Verificar y eliminar archivos de bloqueo obsoletos al inicio
    try:
        lock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup_lock.txt")
        if os.path.exists(lock_file_path):
            logger.warning("Eliminando archivo de bloqueo antiguo al iniciar el servicio")
            os.remove(lock_file_path)
    except Exception as lock_error:
        logger.error(f"Error al eliminar archivo de bloqueo antiguo: {lock_error}")
    
    try:
        # Inicializar administradores de configuración y respaldo
        logger.info("Inicializando ConfigManager para modo servicio")
        config_manager = ConfigManager()
        
        # Forzar reparación del archivo de estado antes de comenzar
        logger.info("Reparando archivo de estado")
        config_manager.repair_state_file()
        
        # Registrar estado actual para diagnóstico
        program_state = config_manager.get_program_state()
        server_data = config_manager.get_server_data()
        
        # Marcar que el servicio está en ejecución
        config_manager.update_program_state(running=True)
        
        # Verificar datos críticos
        if not server_data:
            logger.error("No hay datos de servidor configurados. El servicio no puede iniciar respaldos.")
            # Intentar crear un archivo server.json básico
            if "password" not in server_data:
                logger.warning("Datos de servidor incompletos. Se necesita configurar la aplicación en modo GUI primero.")
        
        # Iniciar programador de respaldos
        success = start_scheduled_backups()
        if success:
            logger.info("Servicio de respaldo iniciado correctamente")
            
            # Variable de control para reintentos
            consecutive_errors = 0
            last_error_time = 0
            
            # Mantener el programa en ejecución con reintentos en caso de errores
            while True:
                try:
                    # Verificar si hay tareas pendientes y ejecutarlas
                    schedule.run_pending()
                    
                    # Si llegamos aquí sin errores, resetear contador
                    if consecutive_errors > 0:
                        logger.info(f"Recuperado después de {consecutive_errors} errores consecutivos")
                        consecutive_errors = 0
                    
                    # Dormir para no consumir CPU
                    time.sleep(10)
                    
                    # Cada 5 minutos, verificar que todo esté bien
                    current_time = time.time()
                    if current_time - last_error_time > 300:  # 5 minutos
                        last_error_time = current_time
                        
                        # Verificar y reparar estado
                        program_state = config_manager.get_program_state()
                        server_data = config_manager.get_server_data()
                        
                        # Asegurar que seguimos programados
                        if not program_state.get("scheduled", False):
                            logger.warning("Estado de programación perdido. Reactivando...")
                            config_manager.update_program_state(scheduled=True)
                            # Reiniciar scheduler
                            try:
                                success = start_scheduled_backups()
                                if success:
                                    logger.info("Scheduler reiniciado con éxito")
                                else:
                                    logger.error("Error al reiniciar scheduler")
                            except Exception as scheduler_error:
                                logger.error(f"Error al reiniciar scheduler: {scheduler_error}", exc_info=True)
                                
                except KeyboardInterrupt:
                    logger.info("Servicio detenido por señal de interrupción")
                    return 0
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error en bucle principal del servicio: {e}", exc_info=True)
                    
                    if consecutive_errors >= 5:
                        # Después de 5 errores consecutivos, intentar reparar la configuración
                        try:
                            logger.warning("Múltiples errores detectados, intentando reparar configuración")
                            config_manager.repair_state_file()
                            # Reiniciar scheduler
                            success = start_scheduled_backups()
                            if success:
                                logger.info("Configuración reparada y scheduler reiniciado")
                                consecutive_errors = 0
                            else:
                                logger.error("Error al reparar configuración")
                        except Exception as repair_error:
                            logger.critical(f"Error al intentar reparar: {repair_error}", exc_info=True)
                
                # Esperar antes del siguiente intento
                backoff_time = min(60, 5 * consecutive_errors)
                time.sleep(backoff_time)
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
                if backup_dir:
                    os.makedirs(backup_dir, exist_ok=True)
                else:
                    logger.error("No se encontró directorio de respaldo configurado")
                    return 1
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
            pass
        return 1

if __name__ == "__main__":
    try:
        exit_code = initialize_app()
        sys.exit(exit_code)
    except Exception as e:
        try:
            logger.critical(f"Error no capturado: {e}", exc_info=True)
        except:
            pass
        sys.exit(1)
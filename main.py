import logging
import sys
import argparse
import os
import time
import datetime
import schedule
from pathlib import Path
from typing import Dict, Any, Optional

# Importar psutil AQUÍ para que PyInstaller lo detecte
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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
    
    # Limpiar handlers existentes para evitar duplicación
    logger.handlers.clear()
    
    # Configurar manejadores de logs
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    
    # Añadir manejador de consola (solo para modo interactivo, no para servicio)
    if not is_service_mode():
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console_handler)
    
    # Evitar propagación al root logger
    logger.propagate = False
    
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

# NO configurar logging.basicConfig aquí - se hace en setup_logging()
# Esto evita duplicación de logs

# NO IMPORTAR NADA AQUÍ - se importa dentro de funciones para evitar
# inicialización prematura en modo servicio

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
        help='Ejecuta la aplicación como servicio Windows (modo legacy/NSSM)'
    )
    parser.add_argument(
        '--native-service',
        action='store_true',
        help='Ejecuta como servicio nativo de Windows (v2.0 con pywin32)'
    )
    return parser.parse_args()

def start_scheduled_backups():
    """Inicia la ejecución de respaldos programados."""
    try:
        from config_manager import ConfigManager
        config_manager = ConfigManager()
        program_state = config_manager.get_program_state()
        
        # Obtener tareas del nuevo sistema
        backup_tasks = config_manager.get_backup_tasks()
        
        # Verificar si hay respaldo programado (legacy o nuevo sistema)
        scheduled = program_state.get("scheduled", False)
        has_tasks = len(backup_tasks) > 0
        
        logger.info(f"Estado de programación: scheduled={scheduled}, tareas={len(backup_tasks)}")
        
        # Obtener directorio de respaldo
        backup_dir = program_state.get("backup_dir")
        
        # Verificar que hay un directorio de respaldo
        if not backup_dir:
            logger.warning("No hay directorio de respaldo configurado")
            backup_dir = os.path.join(APP_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Usando directorio de respaldo predeterminado: {backup_dir}")
            config_manager.update_program_state(backup_dir=backup_dir)
        
        # Asegurar que el directorio existe con permisos adecuados
        try:
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Directorio de respaldo verificado: {backup_dir}")
            
            check_file = os.path.join(backup_dir, "check_write.tmp")
            try:
                with open(check_file, 'w') as f:
                    f.write("check")
                os.remove(check_file)
                logger.info(f"Permiso de escritura en directorio verificado")
            except Exception as write_error:
                logger.error(f"Error de permisos de escritura en {backup_dir}: {write_error}")
                backup_dir = os.path.join(APP_DIR, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                logger.info(f"Cambiando a directorio de respaldo alternativo: {backup_dir}")
                config_manager.update_program_state(backup_dir=backup_dir)
        except Exception as e:
            logger.error(f"Error al verificar directorio de respaldo: {e}")
            backup_dir = os.path.join(APP_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"Usando directorio de respaldo alternativo: {backup_dir}")
            config_manager.update_program_state(backup_dir=backup_dir)
        
        # Verificar si hay servidores configurados
        enabled_servers = config_manager.get_enabled_servers()
        
        if not enabled_servers:
            logger.warning("No hay servidores habilitados configurados")
            server_data = config_manager.get_server_data()
            if server_data:
                logger.info("Migrando desde configuración de servidor único")
                enabled_servers = config_manager.get_enabled_servers()
                if not enabled_servers:
                    logger.error("No se pudo migrar la configuración de servidor")
                    return False
            else:
                logger.error("No hay configuración de servidores disponible")
                return False
        
        # Validar que al menos un servidor tenga configuración válida
        valid_servers = 0
        for server in enabled_servers:
            server_type = server.get("server_type")
            if server_type in ["MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"]:
                if server.get("password") and server.get("client"):
                    valid_servers += 1
        
        if valid_servers == 0:
            logger.error("No hay servidores con configuración válida")
            return False
        
        logger.info(f"Servicio configurado con {len(enabled_servers)} servidor(es) habilitado(s), {valid_servers} válido(s)")
        
        # Configurar programador
        from backup_manager import BackupManager
        backup_manager = BackupManager()
        
        # Función que ejecuta el respaldo
        def execute_backup_safely():
            try:
                current_state = config_manager.get_program_state()
                current_enabled_servers = config_manager.get_enabled_servers()
                
                if not current_enabled_servers:
                    logger.warning("No hay servidores habilitados para ejecutar respaldo")
                    return False
                
                try:
                    backup_directory = current_state.get("backup_dir", backup_dir)
                    amount_value = current_state.get("amount", 5)
                    
                    try:
                        os.makedirs(backup_directory, exist_ok=True)
                        check_file = os.path.join(backup_directory, "check_write.tmp")
                        with open(check_file, 'w') as f:
                            f.write("check")
                        if os.path.exists(check_file):
                            os.remove(check_file)
                        logger.info(f"Directorio de respaldo verificado: {backup_directory}")
                    except Exception as dir_error:
                        logger.error(f"Error de permisos en directorio: {dir_error}")
                        return False
                    
                    logger.info(f"Iniciando respaldo de {len(current_enabled_servers)} servidor(es)")
                    
                    config_manager.update_program_state(
                        running=True,
                        status="in_progress",
                        timestamp=datetime.datetime.now().isoformat()
                    )
                    
                    results = backup_manager.backup_all_servers(
                        backup_dir=backup_directory,
                        amount=amount_value
                    )
                    
                    all_success = all(results.values()) if results else False
                    
                    if all_success and results:
                        config_manager.update_program_state(status="completed", running=True)
                        logger.info(f"Respaldo completado: {len(results)} servidores")
                    else:
                        config_manager.update_program_state(status="error", running=True)
                        failed = sum(1 for v in results.values() if not v)
                        logger.warning(f"Respaldo con {failed} fallos")
                    
                    config_manager.force_save_all()
                    return all_success
                except Exception as exec_error:
                    logger.error(f"Error durante respaldo: {exec_error}", exc_info=True)
                    config_manager.update_program_state(status="error", running=True)
                    return False
            except Exception as e:
                logger.error(f"Error al preparar respaldo: {e}", exc_info=True)
                return False
        
        # Programar tareas
        if has_tasks:
            # Usar nuevo sistema de tareas
            logger.info(f"Configurando {len(backup_tasks)} tarea(s) programada(s)")
            
            tasks_configured = 0
            for idx, task in enumerate(backup_tasks, 1):
                if not task.get("enabled", True):
                    logger.info(f"Tarea {idx} deshabilitada, omitiendo")
                    continue
                
                task_type = task.get("type")
                
                if task_type == "frequency":
                    hours = task.get("hours", 0)
                    minutes = task.get("minutes", 0)
                    total_minutes = (hours * 60) + minutes
                    
                    if total_minutes > 0:
                        backup_manager.scheduler.schedule_backup(hours, minutes, execute_backup_safely)
                        logger.info(f"Tarea {idx} (frecuencia): cada {hours}h:{minutes}m")
                        tasks_configured += 1
                        
                elif task_type == "fixed_time":
                    hour = task.get("hour", 0)
                    minute = task.get("minute", 0)
                    # Para hora fija, usamos schedule directamente
                    import schedule
                    time_str = f"{str(hour).zfill(2)}:{str(minute).zfill(2)}"
                    schedule.every().day.at(time_str).do(execute_backup_safely)
                    logger.info(f"Tarea {idx} (hora fija): a las {time_str}")
                    tasks_configured += 1
            
            if tasks_configured == 0:
                logger.warning("Ninguna tarea configurada correctamente, creando tarea por defecto")
                backup_manager.scheduler.schedule_backup(4, 0, execute_backup_safely)
                config_manager.set_backup_schedule(4, 0, True)
                
        else:
            # Sin tareas, crear tarea por defecto (cada 4 horas)
            logger.info("No hay tareas configuradas, creando tarea por defecto: cada 4 horas")
            config_manager.set_backup_schedule(4, 0, True)
            backup_manager.scheduler.schedule_backup(4, 0, execute_backup_safely)
        
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
    
    # Configurar logger específico para modo servicio (solo si no está configurado ya)
    try:
        # Verificar si ya existe un FileHandler para SERVICE_LOG_FILE
        has_service_handler = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(SERVICE_LOG_FILE)
            for h in logger.handlers
        )
        
        if not has_service_handler:
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
        from config_manager import ConfigManager
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
        from config_manager import ConfigManager
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
                
                # Ejecutar backup de TODOS los servidores habilitados
                logger.info("Ejecutando respaldo inmediato de todos los servidores")
                
                from backup_manager import BackupManager
                backup_manager = BackupManager()
                results = backup_manager.backup_all_servers(
                    backup_dir=program_state["backup_dir"],
                    amount=program_state.get("amount", 5)
                )
                
                if not results:
                    logger.warning("No hay servidores configurados para backup")
                    return 1
                
                # Verificar si todos fueron exitosos
                successful = sum(1 for v in results.values() if v)
                total = len(results)
                
                if successful == total:
                    logger.info(f"Respaldo inmediato completado: {successful}/{total} exitosos")
                    return 0
                else:
                    logger.error(f"Respaldo completado con errores: {successful}/{total} exitosos")
                    return 1
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
        # Detectar modo servicio PRIMERO (antes de cualquier inicialización costosa)
        def is_running_as_service():
            """
            Detecta si el proceso está siendo ejecutado como servicio de Windows.
            Usa múltiples métodos para mayor fiabilidad.
            """
            parent_info = "N/A"
            session_id = -1
            is_interactive = True
            
            # Método 1: Obtener Session ID - servicios corren en sesión 0
            try:
                import ctypes
                pid = os.getpid()
                session = ctypes.c_ulong()
                if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session)):
                    session_id = session.value
            except:
                session_id = -1
            
            # Método 2: Verificar si el proceso tiene una estación de ventanas interactiva
            try:
                import ctypes
                user32 = ctypes.windll.user32
                # GetProcessWindowStation retorna NULL para servicios sin estación
                hwinsta = user32.GetProcessWindowStation()
                is_interactive = hwinsta != 0
            except:
                is_interactive = True
            
            # Método 3: Verificar proceso padre/abuelo
            if PSUTIL_AVAILABLE:
                try:
                    import psutil
                    current = psutil.Process()
                    parent = current.parent()
                    
                    if parent:
                        parent_name = parent.name().lower()
                        grandparent = parent.parent()
                        grandparent_name = grandparent.name().lower() if grandparent else "N/A"
                        parent_info = f"{parent_name} -> {grandparent_name}"
                        
                        # Si el abuelo es services.exe, es servicio
                        if 'services.exe' in grandparent_name:
                            return True, parent_info, session_id
                except:
                    pass
            
            # Decisión final: Es servicio si sesión 0 Y no hay argumentos de comando
            # Los comandos install/remove/start/stop siempre tienen argumentos
            if session_id == 0 and len(sys.argv) == 1:
                return True, f"{parent_info} (sesión 0, sin args)", session_id
                
            return False, parent_info, session_id
        
        # Verificar argumentos de línea de comandos para comandos de servicio
        # El formato correcto es: --native-service install/remove/start/stop
        service_commands = ['install', 'remove', 'start', 'stop', 'restart', 'debug', 'update']
        has_native_service_flag = '--native-service' in sys.argv
        has_service_command = any(arg.lower() in service_commands for arg in sys.argv[1:])
        
        # Si se detecta --native-service O si está siendo ejecutado como servicio (sesión 0)
        is_service_result, parent_info, session_id = is_running_as_service()
        is_service_call = has_native_service_flag or is_service_result or (has_service_command and len(sys.argv) == 2)
        
        # DEBUG: Escribir a archivo para diagnóstico (sin logging configurado aún)
        try:
            with open(os.path.join(APP_DIR, "logs", "service_debug.txt"), "a") as f:
                f.write(f"\n{datetime.datetime.now()}: sys.argv = {sys.argv}\n")
                f.write(f"is_service_call = {is_service_call}\n")
                f.write(f"is_service_result = {is_service_result}\n")
                f.write(f"has_native_service_flag = {has_native_service_flag}\n")
                f.write(f"has_service_command = {has_service_command}\n")
                f.write(f"parent_info = {parent_info}\n")
                f.write(f"session_id = {session_id}\n")
                f.write(f"len(sys.argv) = {len(sys.argv)}\n")
        except:
            pass
        
        if is_service_call:
            try:
                from windows_service import MethodoRespaldoService, is_pywin32_available
                
                if not is_pywin32_available():
                    # Inicializar para modo legacy
                    setup_logging()
                    ensure_app_directories()
                    logger.error("pywin32 no disponible - usando modo servicio legacy")
                    return run_as_service()
                
                # Remover --native-service de sys.argv si está presente
                if '--native-service' in sys.argv:
                    sys.argv.remove('--native-service')
                
                # Iniciar servicio nativo
                import win32serviceutil
                import servicemanager
                
                # Si solo queda el ejecutable en sys.argv, el SCM está iniciando el servicio
                if len(sys.argv) == 1:
                    # DEBUG
                    try:
                        with open(os.path.join(APP_DIR, "logs", "service_debug.txt"), "a") as f:
                            f.write(f"LLAMANDO StartServiceCtrlDispatcher...\n")
                    except:
                        pass
                    
                    # CRÍTICO: Llamar a StartServiceCtrlDispatcher INMEDIATAMENTE
                    # La inicialización se hará dentro de SvcRun()
                    servicemanager.Initialize()
                    servicemanager.PrepareToHostSingle(MethodoRespaldoService)
                    servicemanager.StartServiceCtrlDispatcher()
                    return 0
                else:
                    # Si hay argumentos (install, remove, debug, etc), inicializar normalmente
                    setup_logging()
                    ensure_app_directories()
                    logger.info(f"Ejecutando comando: {' '.join(sys.argv[1:])}")
                    win32serviceutil.HandleCommandLine(MethodoRespaldoService)
                    return 0
                
            except ImportError as e:
                setup_logging()
                ensure_app_directories()
                logger.error(f"Error importando windows_service: {e}")
                logger.info("Cambiando a modo servicio legacy...")
                return run_as_service()
            except Exception as e:
                setup_logging()
                ensure_app_directories()
                logger.error(f"Error en servicio nativo: {e}", exc_info=True)
                return 1
        
        # Para modos NO servicio, inicializar normalmente
        setup_logging()
        ensure_app_directories()
        
        # Procesar argumentos normales
        args = parse_arguments()
        
        # Si se solicita ejecución como servicio (modo legacy/NSSM para compatibilidad v1.0)
        if args.service or is_service_mode():
            logger.info("Iniciando en modo servicio legacy (compatibilidad v1.0)")
            return run_as_service()
        
        # Si se solicita respaldo inmediato
        if args.backup_now:
            return run_backup_immediate()
        
        # Importar GUI solo cuando se necesita (evita bloqueo en modo servicio)
        from views import create_login_interface
        
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
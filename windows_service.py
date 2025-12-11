"""
Módulo para ejecutar MethodoRespaldo como servicio nativo de Windows
Usa pywin32 para implementar la API de Windows Service
Compatible con Windows Server 2008+ y Windows 7+
"""

import sys
import os
import time
import logging
from pathlib import Path
from typing import Any

# Intentar importar pywin32
PYWIN32_AVAILABLE = False
win32serviceutil: Any = None
win32service: Any = None
win32event: Any = None
servicemanager: Any = None

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    PYWIN32_AVAILABLE = True
except ImportError:
    print("ADVERTENCIA: pywin32 no está disponible. El modo servicio nativo no funcionará.")

# Configurar logging para el servicio
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
SERVICE_LOG = LOG_DIR / "windows_service.log"

# Solo configurar el logger del servicio si no está configurado ya
logger = logging.getLogger("WindowsService")
if not logger.handlers:
    # Solo agregar handlers si no existen
    handler = logging.FileHandler(SERVICE_LOG, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Evitar que los logs se propaguen al root logger
    logger.propagate = False


# Solo definir la clase si pywin32 está disponible
if PYWIN32_AVAILABLE and win32serviceutil is not None:
    class MethodoRespaldoService(win32serviceutil.ServiceFramework):
        """
        Servicio de Windows para MethodoRespaldo
        Implementa la API nativa de Windows Service usando pywin32
        """
        
        # Información del servicio
        _svc_name_ = "MethodoRespaldo"
        _svc_display_name_ = "Methodo Respaldo - Sistema de Backups v2.0"
        _svc_description_ = "Sistema automatizado de respaldo de bases de datos MySQL y SQL Server"
        
        def __init__(self, args):
            """Inicializa el servicio de Windows"""
            win32serviceutil.ServiceFramework.__init__(self, args)
            
            # Crear evento de parada
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = False
            
            # Configurar directorio de trabajo
            if getattr(sys, 'frozen', False):
                # Ejecutable compilado
                self.app_dir = Path(sys.executable).parent
            else:
                # Modo desarrollo
                self.app_dir = Path(__file__).parent
            
            os.chdir(self.app_dir)
        
        def SvcStop(self):
            """
            Llamado cuando Windows solicita detener el servicio
            """
            logger.info("Recibida señal de parada del servicio")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            
            # Señalar al hilo principal que debe detenerse
            win32event.SetEvent(self.stop_event)
            self.running = False
            
            logger.info("Servicio detenido correctamente")
        
        def SvcDoRun(self):
            """
            Punto de entrada principal cuando el servicio inicia
            """
            try:
                # CRÍTICO: Inicializar logging y directorios AQUÍ (después de StartServiceCtrlDispatcher)
                import sys
                import os
                from pathlib import Path
                
                # Asegurar directorios ANTES de configurar logging
                if getattr(sys, 'frozen', False):
                    app_dir = Path(sys.executable).parent
                else:
                    app_dir = Path(__file__).parent
                    
                for directory in ['logs', 'temp', 'assets']:
                    dir_path = app_dir / directory
                    dir_path.mkdir(exist_ok=True)
                
                # Reconfigurar logger para asegurar que funciona
                service_log = app_dir / "logs" / "windows_service.log"
                
                # Limpiar handlers existentes
                logger.handlers.clear()
                
                # Crear nuevo handler con la ruta correcta
                handler = logging.FileHandler(service_log, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                logger.propagate = False
                
                logger.info(f"Servicio MethodoRespaldo v2.0 iniciado - {self.app_dir}")
                logger.info(f"Directorio de trabajo: {os.getcwd()}")
                logger.info(f"Directorio del ejecutable: {app_dir}")
                
                # Reportar al SCM que estamos iniciando
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, '')
                )
                
                logger.info("Reportado al Service Control Manager")
                
                # Marcar como en ejecución
                self.running = True
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                
                logger.info("Estado cambiado a SERVICE_RUNNING")
                
                # Ejecutar la lógica principal del servicio
                logger.info("Iniciando loop principal del servicio")
                self._run_service_loop()
                
            except Exception as e:
                logger.error(f"Error crítico en el servicio: {e}", exc_info=True)
                servicemanager.LogErrorMsg(f"Error en MethodoRespaldo: {e}")
                self.SvcStop()
        
        def _run_service_loop(self):
            """
            Loop principal del servicio
            Importa y ejecuta la lógica de respaldo
            """
            try:
                logger.info("Iniciando importación de módulos...")
                
                # Importar módulos necesarios (lazy import para evitar problemas de inicialización)
                from backup_manager import BackupManager
                from config_manager import ConfigManager
                import schedule
                
                logger.info("Módulos importados correctamente")
                
                # Inicializar managers
                logger.info("Inicializando ConfigManager...")
                config_manager = ConfigManager()
                
                logger.info("Inicializando BackupManager...")
                backup_manager = BackupManager()
                
                logger.info("Managers inicializados correctamente")
                
                # Obtener configuración de programación
                logger.info("Obteniendo configuración de programación...")
                program_state = config_manager.get_program_state()
                
                if not program_state:
                    logger.warning("No se encontró configuración. Usando valores por defecto.")
                    backup_hours = 4  # Por defecto cada 4 horas
                    backup_minutes = 0
                else:
                    backup_hours = program_state.get('backup_hours', 4)
                    backup_minutes = program_state.get('backup_minutes', 0)
                    logger.info(f"Configuración cargada: backup cada {backup_hours}h:{backup_minutes}m")
                
                # Calcular intervalo total en minutos
                total_minutes = (backup_hours * 60) + backup_minutes
                
                # Asegurar un mínimo de 1 minuto
                if total_minutes < 1:
                    logger.warning(f"Intervalo muy pequeño ({total_minutes}m), usando mínimo de 1 minuto")
                    total_minutes = 1
                
                # Programar backup por intervalo en minutos para mayor precisión
                logger.info(f"Programando backup cada {total_minutes} minuto(s) ({backup_hours}h:{backup_minutes}m)")
                schedule.every(total_minutes).minutes.do(self._execute_backup, backup_manager)
                
                logger.info(f"Backup programado: cada {backup_hours}h:{backup_minutes}m ({total_minutes} minutos)")
                logger.info("Ejecutando primer backup inmediatamente...")
                
                # Ejecutar el primer backup inmediatamente al iniciar el servicio
                self._execute_backup(backup_manager)
                
                # Loop principal
                while self.running:
                    # Ejecutar tareas pendientes
                    schedule.run_pending()
                    
                    # Esperar 60 segundos o hasta que se señale parada
                    # Usar WaitForSingleObject permite respuesta rápida a señales de parada
                    result = win32event.WaitForSingleObject(self.stop_event, 60000)  # 60 segundos
                    
                    if result == win32event.WAIT_OBJECT_0:
                        # Evento de parada señalado
                        break
                
                logger.info("Servicio finalizado")
                
            except ImportError as e:
                logger.error(f"Error importando módulos: {e}", exc_info=True)
                logger.error("Asegúrese de que todos los módulos estén en el mismo directorio")
            except Exception as e:
                logger.error(f"Error en el loop del servicio: {e}", exc_info=True)
        
        def _execute_backup(self, backup_manager):
            """
            Ejecuta un backup programado de todos los servidores habilitados
            """
            try:
                from config_manager import ConfigManager
                config_manager = ConfigManager()
                program_state = config_manager.get_program_state()
                
                backup_dir = program_state.get("backup_dir")
                amount = program_state.get("amount", 5)
                
                if not backup_dir:
                    logger.error("No hay directorio de backup configurado")
                    return
                
                # Ejecutar backup de todos los servidores
                results = backup_manager.backup_all_servers(
                    backup_dir=backup_dir,
                    amount=amount
                )
                
                if not results:
                    logger.warning("No hay servidores configurados")
                    return
                
                # Resumen
                successful = sum(1 for v in results.values() if v)
                total = len(results)
                
                if successful == total:
                    logger.info(f"Backup completado: {successful}/{total} exitosos")
                else:
                    logger.warning(f"Backup parcial: {successful}/{total} exitosos")
                    
            except Exception as e:
                logger.error(f"Error ejecutando backup: {e}", exc_info=True)


def install_service():
    """
    Instala el servicio de Windows
    Usar desde línea de comandos: python windows_service.py install
    """
    if not PYWIN32_AVAILABLE:
        print("ERROR: pywin32 no está disponible. No se puede instalar el servicio.")
        return False
    
    if 'MethodoRespaldoService' not in globals():
        print("ERROR: Clase MethodoRespaldoService no está definida.")
        return False
    
    try:
        win32serviceutil.HandleCommandLine(MethodoRespaldoService)  # type: ignore
        return True
    except Exception as e:
        logger.error(f"Error instalando servicio: {e}")
        return False


def is_pywin32_available():
    """Verifica si pywin32 está disponible"""
    return PYWIN32_AVAILABLE


if __name__ == '__main__':
    if not PYWIN32_AVAILABLE:
        print("="*60)
        print("ERROR: pywin32 no está instalado")
        print("="*60)
        print("Instale pywin32 con: pip install pywin32")
        print("O ejecute: python -m pip install pywin32")
        sys.exit(1)
    
    if 'MethodoRespaldoService' not in globals():
        print("="*60)
        print("ERROR: Clase MethodoRespaldoService no está definida")
        print("="*60)
        sys.exit(1)
    
    # Manejar comandos de línea (install, start, stop, remove, etc.)
    win32serviceutil.HandleCommandLine(MethodoRespaldoService)  # type: ignore

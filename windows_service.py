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
                logger.info(f"Servicio MethodoRespaldo v2.0 iniciado - {self.app_dir}")
                
                # Reportar al SCM que estamos iniciando
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, '')
                )
                
                # Marcar como en ejecución
                self.running = True
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                
                # Ejecutar la lógica principal del servicio
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
                # Importar módulos necesarios (lazy import para evitar problemas de inicialización)
                from backup_manager import BackupManager
                from config_manager import ConfigManager
                import schedule
                
                # Inicializar managers
                config_manager = ConfigManager()
                backup_manager = BackupManager()
                
                # Obtener configuración de programación
                program_state = config_manager.get_program_state()
                
                if not program_state:
                    logger.warning("No se encontró configuración. Usando valores por defecto.")
                    backup_hour = 4
                    backup_minute = 0
                else:
                    backup_hour = program_state.get('backup_hours', 4)
                    backup_minute = program_state.get('backup_minutes', 0)
                
                # Programar backup diario
                schedule_time = f"{backup_hour:02d}:{backup_minute:02d}"
                schedule.every().day.at(schedule_time).do(self._execute_backup, backup_manager)
                
                logger.info(f"Backup programado: {schedule_time} diario")
                
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
            Ejecuta un backup programado
            """
            try:
                result = backup_manager.backup_database()
                
                if result:
                    logger.info("Backup completado")
                else:
                    logger.error("Backup falló")
                    
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

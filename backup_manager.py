"""
Módulo para gestionar los respaldos de bases de datos.
Centraliza todas las operaciones relacionadas con la creación,
programación y gestión de respaldos.
"""

import os
import socket
import datetime
import subprocess
import threading
import schedule
import time
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Tuple

from functions import (
    decrypt, send_email, manage_backup_limit, find_mysql_bin_path, 
    find_7zip_path, KEY, DATABASE, USER, BACKUP_PASSWORD, logger
)

class BackupScheduler:
    """Gestor de programación de respaldos."""
    
    def __init__(self):
        """Inicializa el programador de respaldos."""
        self.running = True
        self.scheduled = False
        self._lock = threading.Lock()
        self.scheduler_thread = None
        self._last_execution = 0  # Timestamp del último respaldo
        self._missed_executions = 0  # Contador de ejecuciones perdidas
        
        # Semáforo para controlar ejecuciones simultáneas
        self._backup_semaphore = threading.Semaphore(1)
        
        # ID único para esta instancia del scheduler
        self._instance_id = f"scheduler_{os.getpid()}_{int(time.time())}"
        self._is_backup_running = False
        
        # Archivo para controlar concurrencia entre procesos
        self._lock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup_lock.txt")
    
    def _acquire_process_lock(self, timeout=30) -> bool:
        """
        Adquiere un bloqueo a nivel de proceso para evitar respaldos simultáneos.
        
        Args:
            timeout: Tiempo máximo de espera en segundos
            
        Returns:
            True si se adquirió el bloqueo, False en caso contrario
        """
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                # Verificar si el archivo de bloqueo existe y es reciente
                if os.path.exists(self._lock_file_path):
                    # Verificar la antigüedad del archivo de bloqueo
                    file_time = os.path.getmtime(self._lock_file_path)
                    current_time = time.time()
                    
                    # Si el archivo tiene más de 30 minutos, considerarlo obsoleto
                    if (current_time - file_time) > 1800:  # 30 minutos
                        logger.warning("Encontrado archivo de bloqueo obsoleto. Forzando desbloqueo.")
                        self._release_process_lock()
                    else:
                        logger.warning("Otro proceso está ejecutando un respaldo. Esperando...")                       
                        # Esperar un tiempo antes de reintentar
                        time.sleep(5)
                        continue
                
                # Crear archivo de bloqueo con información de la instancia
                lock_info = f"{self._instance_id} - {datetime.datetime.now().isoformat()}"
                
                # Asegurar que el directorio existe
                os.makedirs(os.path.dirname(self._lock_file_path), exist_ok=True)
                
                with open(self._lock_file_path, 'w') as f:
                    f.write(lock_info)
                
                logger.debug(f"Bloqueo de proceso adquirido: {lock_info}")
                return True
                
            except Exception as e:
                logger.error(f"Error al adquirir bloqueo de proceso: {e}")
                time.sleep(1)
        
        logger.warning(f"No se pudo adquirir el bloqueo de proceso después de {timeout} segundos")
        return False
    
    def _release_process_lock(self) -> bool:
        """
        Libera el bloqueo a nivel de proceso.
        
        Returns:
            True si se liberó el bloqueo, False en caso contrario
        """
        try:
            if os.path.exists(self._lock_file_path):
                os.remove(self._lock_file_path)
                logger.debug("Bloqueo de proceso liberado")
            return True
        except Exception as e:
            logger.error(f"Error al liberar bloqueo de proceso: {e}")
            return False
    
    def schedule_backup(
        self, 
        hours: int, 
        minutes: int, 
        backup_func: Callable, 
        *args, 
        **kwargs
    ) -> None:
        """
        Programa un respaldo automático.
        
        Args:
            hours: Horas entre respaldos
            minutes: Minutos entre respaldos
            backup_func: Función de respaldo a ejecutar
            *args: Argumentos posicionales para la función de respaldo
            **kwargs: Argumentos nombrados para la función de respaldo
        """
        with self._lock:
            # Validar parámetros
            try:
                hours = int(hours)
                minutes = int(minutes)
            except (ValueError, TypeError):
                logger.warning(f"Valores inválidos para programación: {hours}h:{minutes}m - Usando predeterminados")
                hours = 4  # Predeterminado: cada 4 horas 
                minutes = 0
            
            # Validar rango
            if hours < 0 or hours > 23:
                logger.warning(f"Valor de horas fuera de rango: {hours} - Corrigiendo")
                hours = max(0, min(hours, 23))
                
            if minutes < 0 or minutes > 59:
                logger.warning(f"Valor de minutos fuera de rango: {minutes} - Corrigiendo")
                minutes = max(0, min(minutes, 59))
            
            # Limpiar programaciones anteriores (muy importante para evitar duplicados)
            schedule.clear()
            logger.info("Limpiadas todas las tareas anteriores del programador")
            
            # Calcular intervalo en segundos
            interval_seconds = (hours * 3600) + (minutes * 60)
            if interval_seconds <= 0:
                logger.warning("Intervalo de respaldo demasiado pequeño, ajustando a 4 horas")
                interval_seconds = 14400  # 4 horas como mínimo
                
            logger.info(f"Programando respaldo cada {interval_seconds} segundos ({hours}h:{minutes}m)")
            
            # Función wrapper para mejorar el manejo de errores y concurrencia
            def safe_backup_execution():
                # Verificar si ya hay un respaldo en ejecución (semáforo en memoria)
                if not self._backup_semaphore.acquire(blocking=False):
                    logger.warning("Ya hay un respaldo en ejecución. Omitiendo esta ejecución.")
                    return False
                
                # Verificar si hay un respaldo en ejecución en otro proceso
                if not self._acquire_process_lock():
                    logger.warning("Ya hay un respaldo en ejecución en otro proceso. Omitiendo esta ejecución.")
                    self._backup_semaphore.release()
                    return False
                
                try:
                    logger.info(f"Ejecutando respaldo programado ({hours}h:{minutes}m)")
                    self._last_execution = time.time()
                    self._is_backup_running = True
                    
                    # Ejecutar el respaldo real
                    result = backup_func(*args, **kwargs)
                    
                    if result:
                        logger.info("Respaldo programado completado exitosamente")
                        self._missed_executions = 0  # Resetear contador de fallos
                    else:
                        logger.error("Respaldo programado falló")
                        self._missed_executions += 1
                    
                    return result
                    
                except Exception as e:
                    self._missed_executions += 1
                    logger.error(f"Error al ejecutar respaldo programado: {e}", exc_info=True)
                    # No propagar la excepción para evitar que se interrumpa el scheduler
                    return False
                finally:
                    # Siempre liberar recursos
                    self._is_backup_running = False
                    self._release_process_lock()
                    self._backup_semaphore.release()
            
            # Programar nueva tarea con wrapper de seguridad
            job = schedule.every(interval_seconds).seconds.do(safe_backup_execution)
            job.tag("scheduled_backup")
            
            # Marcar como programado
            self.scheduled = True
            
            # Programar un primer respaldo para prueba (después de 1 minuto)
            if hours > 1 or (hours == 1 and minutes > 10):
                logger.info("Programando respaldo inicial de prueba en 1 minuto")
                test_job = schedule.every(1).minutes.do(safe_backup_execution)
                test_job.tag("test_backup")
                
                # Eliminar la tarea de prueba después de ejecutarse
                def remove_test_task():
                    try:
                        for job in schedule.get_jobs("test_backup"):
                            schedule.cancel_job(job)
                        logger.info("Tarea de prueba eliminada")
                    except Exception as e:
                        logger.error(f"Error al eliminar tarea de prueba: {e}")
                
                # Programar eliminación de la tarea de prueba
                cleanup_job = schedule.every(2).minutes.do(remove_test_task)
                cleanup_job.tag("cleanup")
            
            # Si no hay un hilo de scheduler en ejecución, iniciarlo
            if self.scheduler_thread is None or not self.scheduler_thread.is_alive():
                self.start_scheduler_thread()

    def start_scheduler_thread(self):
        """Inicia el hilo del programador si no está en ejecución."""
        if self.scheduler_thread is None or not self.scheduler_thread.is_alive():
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            logger.info("Hilo del programador de respaldos iniciado")

    def _run_scheduler(self) -> None:
        """Ejecuta el programador de tareas en un bucle."""
        logger.info("Iniciando programador de respaldos")
        while self.running and self.scheduled:
            try:
                schedule.run_pending()
                
                # Verificar si han pasado más de 5 minutos desde la última ejecución programada
                current_time = time.time()
                jobs = schedule.get_jobs("scheduled_backup")
                
                if jobs and self._last_execution > 0:
                    job = jobs[0]
                    # Calcular tiempo que debería haber pasado
                    # Si han pasado más del doble del tiempo programado, puede haber un problema
                    if self._missed_executions > 3:
                        logger.warning(f"Detectadas {self._missed_executions} ejecuciones perdidas. Reiniciando scheduler.")
                        # Reiniciar job
                        schedule.clear("scheduled_backup")
                        job = schedule.every(job.interval).seconds.do(job.job_func)
                        job.tag("scheduled_backup")
                        self._missed_executions = 0
                        logger.info("Scheduler reiniciado después de detectar ejecuciones perdidas")
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error en el bucle del programador: {e}", exc_info=True)
                # Pequeña pausa antes de continuar para evitar bucles de error muy rápidos
                time.sleep(5)
        logger.info("Programador de respaldos detenido")
    
    def stop(self) -> None:
        """Detiene el programador de respaldos."""
        with self._lock:
            self.running = False
            self.scheduled = False
            logger.info("Programador de respaldos marcado para detenerse")
            
            # Si hay un respaldo en ejecución, esperar a que termine
            if self._is_backup_running:
                logger.info("Esperando a que termine el respaldo en ejecución...")
                # No esperar indefinidamente
                timeout = 300  # 5 minutos máximo
                start_time = time.time()
                while self._is_backup_running and (time.time() - start_time) < timeout:
                    time.sleep(1)
    
    def is_scheduled(self) -> bool:
        """
        Verifica si hay respaldos programados.
        
        Returns:
            True si hay respaldos programados, False en caso contrario
        """
        with self._lock:
            return self.scheduled

    def restart_if_needed(self) -> bool:
        """
        Reinicia el programador si no está funcionando correctamente.
        
        Returns:
            True si se reinició, False si no fue necesario
        """
        with self._lock:
            if not self.scheduled:
                logger.warning("Scheduler no está programado. Reiniciando...")
                self.scheduled = True
                self.running = True
                self.start_scheduler_thread()
                return True
                
            if self.scheduler_thread is None or not self.scheduler_thread.is_alive():
                logger.warning("Hilo del scheduler no está en ejecución. Reiniciando...")
                self.start_scheduler_thread()
                return True
                
            return False

class BackupManager:
    """Gestor de respaldos de bases de datos."""
    
    def __init__(self):
        """Inicializa el gestor de respaldos."""
        self.scheduler = BackupScheduler()
    
    def backup_mysql_database(
        self,
        password: str, 
        backup_dir: str, 
        client: str, 
        amount: int,
        server_data: Dict[str, Any],
        update_callback: Optional[Callable[[int, str], None]] = None
    ) -> bool:
        """
        Realiza un respaldo de la base de datos MySQL.
        
        Args:
            password: Contraseña encriptada del servidor MySQL
            backup_dir: Directorio donde se almacenará el backup
            client: Nombre del cliente
            amount: Cantidad máxima de backups a mantener
            server_data: Datos del servidor
            update_callback: Función de callback para actualizar el progreso
            
        Returns:
            True si el backup fue exitoso, False en caso contrario
        """
        try:
            # Validar parámetros de entrada
            backup_path = Path(backup_dir)
            if not backup_path.is_dir():
                try:
                    backup_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Directorio de respaldo creado: {backup_dir}")
                except Exception as e:
                    raise ValueError(f"No se pudo crear el directorio {backup_dir}: {e}")
            
            if not client:
                raise ValueError("Se requiere un nombre de cliente válido")
            
            # Preparar nombres de archivos y rutas
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
            timestamp_email = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}"
            
            decrypted_password = decrypt(KEY, password).decode("utf-8")
            
            # Sanitizar nombre del cliente para el archivo
            client = client.replace(" ", "_").replace("/", "_").replace("\\", "_")
            device = socket.gethostname()
            
            # Generar nombres únicos para los archivos
            unique_id = str(uuid.uuid4())[:8]
            backup_file_name = f"{client}_{device}_backup_{timestamp}.sql"
            
            # Detectar rutas automáticamente
            mysql_bin_path = find_mysql_bin_path()
            seven_zip_path = find_7zip_path()
            
            # Verificar que las rutas existan
            if not mysql_bin_path:
                raise FileNotFoundError("No se pudo encontrar la instalación de MySQL")
            
            if not seven_zip_path:
                raise FileNotFoundError("No se pudo encontrar la instalación de 7-Zip")

            # Cambiar al directorio de MySQL y ejecutar el backup
            if update_callback:
                update_callback(10, "Iniciando respaldo...")
            
            # Crear directorio temporal para respaldo
            # Usar directorio temporal del sistema en lugar de ./temp
            temp_dir = Path(tempfile.gettempdir()) / f"methodo_backup_{unique_id}"
            try:
                temp_dir.mkdir(exist_ok=True, parents=True)
                logger.info(f"Directorio temporal creado: {temp_dir}")
            except Exception as temp_dir_error:
                logger.error(f"Error al crear directorio temporal: {temp_dir_error}")
                # Intentar usar un directorio alternativo
                temp_dir = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp"))
                temp_dir.mkdir(exist_ok=True, parents=True)
                logger.info(f"Usando directorio temporal alternativo: {temp_dir}")
            
            # Usar un nombre único para evitar conflictos
            temp_backup_name = f"{client}_{device}_backup_{timestamp}_{unique_id}.sql"
            temp_backup_path = temp_dir / temp_backup_name
            
            logger.info(f"Iniciando respaldo SQL en {temp_backup_path}")
            
            mysqldump_cmd = [
                str(mysql_bin_path / "mysqldump"),
                "-e", "-R",
                "-u", USER,
                f"-p{decrypted_password}",
                DATABASE,
                f"--result-file={temp_backup_path}"
            ]
            
            # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
            safe_cmd = ' '.join(mysqldump_cmd).replace(decrypted_password, "********")
            logger.info(f"Ejecutando: {safe_cmd}")
            
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                # Crear información de startupinfo para ocultar ventanas en Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.run(
                mysqldump_cmd, 
                shell=False, 
                capture_output=True, 
                text=True,
                check=False,  # No lanzar excepción para manejarla nosotros
                startupinfo=startupinfo
            )
            
            if process.returncode != 0:
                logger.error(f"Error en mysqldump: {process.stderr}")
                raise subprocess.CalledProcessError(process.returncode, safe_cmd, 
                                                output=process.stdout, stderr=process.stderr)
            
            # Esperar a que el proceso libere el archivo
            time.sleep(1)
            
            # Verificar que el archivo se creó correctamente
            if not temp_backup_path.exists() or temp_backup_path.stat().st_size == 0:
                raise ValueError(f"No se pudo crear el archivo de respaldo: {temp_backup_path}")

            if update_callback:
                update_callback(50, "Comprimiendo respaldo...")

            # Verificar que el directorio destino tenga permisos de escritura
            try:
                test_file = backup_path / "test_write.tmp"
                with open(test_file, 'w') as f:
                    f.write("test")
                if test_file.exists():
                    test_file.unlink()
                logger.info(f"Permisos de escritura verificados en: {backup_path}")
            except Exception as e:
                logger.error(f"Sin permisos de escritura en {backup_path}: {e}")
                raise ValueError(f"No se tienen permisos de escritura en el directorio de respaldo: {backup_path}")

            # Generar un nombre único para el archivo comprimido para evitar conflictos
            timestamp_with_millis = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]
            process_id = os.getpid()  # Añadir ID de proceso para mayor unicidad
            seven_zip_file_name = f"{client}_{device}_backup_{timestamp_with_millis}_{process_id}.7z"
            seven_zip_file_path = backup_path / seven_zip_file_name

            # Asegurarse de que no exista un archivo con el mismo nombre
            if seven_zip_file_path.exists():
                try:
                    # Intentar eliminar el archivo existente
                    seven_zip_file_path.unlink()
                    logger.info(f"Archivo existente eliminado: {seven_zip_file_path}")
                except Exception as e:
                    # Si no se puede eliminar, usar un nombre alternativo
                    unique_id = str(uuid.uuid4())[:8]
                    seven_zip_file_name = f"{client}_{device}_backup_{timestamp_with_millis}_{process_id}_{unique_id}.7z"
                    seven_zip_file_path = backup_path / seven_zip_file_name
                    logger.warning(f"No se pudo eliminar archivo existente, usando nombre alternativo: {seven_zip_file_path}")

            # Comprimir con 7-Zip
            logger.info(f"Comprimiendo respaldo en {seven_zip_file_path}")

            # Construir comando 7-Zip con opciones seguras
            compress_cmd = [
                str(seven_zip_path / "7z.exe"),
                "a",                           # Añadir a archivo
                "-y",                          # Asumir "sí" para todas las preguntas
                f"-p{BACKUP_PASSWORD}",        # Contraseña
                str(seven_zip_file_path),      # Archivo destino
                str(temp_backup_path)          # Archivo a comprimir
            ]

            # Ejecutar el comando de forma segura
            safe_compress_cmd = ' '.join(compress_cmd).replace(BACKUP_PASSWORD, "********")
            logger.info(f"Ejecutando: {safe_compress_cmd}")

            # Crear startupinfo para ocultar ventanas de consola
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            # Intentar comprimir con múltiples reintentos si es necesario
            max_compression_retries = 3
            for retry in range(max_compression_retries):
                try:
                    seven_zip_process = subprocess.run(
                        compress_cmd, 
                        shell=False, 
                        capture_output=True, 
                        text=True,
                        check=False,
                        startupinfo=startupinfo,
                        timeout=300  # 5 minutos máximo
                    )
                    
                    # Verificar resultado
                    if seven_zip_process.returncode == 0:
                        logger.info("Compresión 7-Zip exitosa")
                        break
                    else:
                        # Si falló, pero estamos en el último intento, lanzar excepción
                        if retry == max_compression_retries - 1:
                            logger.error(f"Error en 7-Zip después de {max_compression_retries} intentos: {seven_zip_process.stderr}")
                            raise subprocess.CalledProcessError(
                                seven_zip_process.returncode, 
                                safe_compress_cmd,
                                output=seven_zip_process.stdout, 
                                stderr=seven_zip_process.stderr
                            )
                        else:
                            # Si no es el último intento, esperar y reintentar
                            logger.warning(f"Error en 7-Zip (intento {retry+1}): {seven_zip_process.stderr}")
                            time.sleep((retry + 1) * 2)  # Esperar más tiempo en cada reintento
                except subprocess.TimeoutExpired:
                    logger.error("Timeout durante la compresión")
                    if retry == max_compression_retries - 1:
                        raise ValueError("La compresión no pudo completarse por timeout después de múltiples intentos")
                    else:
                        time.sleep((retry + 1) * 2)
                except Exception as e:
                    logger.error(f"Excepción durante la compresión: {e}")
                    if retry == max_compression_retries - 1:
                        raise
                    else:
                        time.sleep((retry + 1) * 2)

            # Verificar que el archivo comprimido se creó correctamente
            if not seven_zip_file_path.exists():
                raise ValueError(f"El archivo comprimido no fue creado: {seven_zip_file_path}")

            # Verificar tamaño del archivo comprimido
            file_size = seven_zip_file_path.stat().st_size
            if file_size == 0:
                raise ValueError(f"El archivo comprimido está vacío: {seven_zip_file_path}")

            logger.info(f"Archivo comprimido creado: {seven_zip_file_path} ({file_size} bytes)")

            if update_callback:
                update_callback(70, "Eliminando archivo temporal...")

            # Eliminar archivo temporal con reintentos
            max_delete_retries = 5
            for retry in range(max_delete_retries):
                try:
                    # Asegurar que los procesos han terminado
                    if 'seven_zip_process' in locals() and seven_zip_process:
                        try:
                            if hasattr(seven_zip_process, 'kill'):
                                seven_zip_process.kill()
                        except:
                            pass
                            
                    # Esperar un momento antes de intentar eliminar
                    time.sleep(1)
                    
                    if temp_backup_path.exists():
                        temp_backup_path.unlink()
                        logger.info(f"Archivo temporal eliminado: {temp_backup_path}")
                        break
                    else:
                        logger.info(f"Archivo temporal ya no existe: {temp_backup_path}")
                        break
                except Exception as e:
                    if retry < max_delete_retries - 1:
                        logger.warning(f"Error al eliminar archivo temporal (intento {retry+1}): {e}")
                        time.sleep((retry + 1) * 2)  # Aumentar tiempo de espera con cada reintento
                    else:
                        logger.error(f"No se pudo eliminar el archivo temporal después de {max_delete_retries} intentos")
                        # No fallar el respaldo por esto, continuar
            
            # Intentar eliminar el directorio temporal
            try:
                # Intentar eliminar el directorio temporal si está vacío
                temp_dir.rmdir()
                logger.info(f"Directorio temporal eliminado: {temp_dir}")
            except Exception as dir_error:
                logger.warning(f"No se pudo eliminar el directorio temporal: {dir_error}")
                # No fallar por esto
            
            if update_callback:
                update_callback(100, "Respaldo completado.")
            
            # Verificar que el archivo zip se creó correctamente
            if not seven_zip_file_path.exists() or seven_zip_file_path.stat().st_size == 0:
                raise ValueError(f"No se pudo crear el archivo de respaldo comprimido: {seven_zip_file_path}")
            
            # Enviar correo de confirmación
            success_message = f"""
            Estimados, informamos que el respaldo de datos programado 
            para el dia de hoy, {timestamp_email}, se ha realizado y completado con exito.

            Saluda atentamente,
            Mesa de ayuda Methodo.
            """
            send_email(client, success_message)
            
            # Gestionar límite de respaldos
            manage_backup_limit(backup_dir, amount)
            
            logger.info(f"Respaldo completado con éxito: {seven_zip_file_path}")
            return True
            
        except Exception as e:
            error_message = f"Error en el proceso de respaldo: {e}"
            logger.error(error_message, exc_info=True)
            send_email(client, f"Error ocurrido al respaldar datos: {e}")
            return False
    
    def decrypt_backup_file(
        self, 
        zip_path: str, 
        password: str, 
        output_dir: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Desencripta un archivo de respaldo 7z
        
        Args:
            zip_path: Ruta del archivo 7z
            password: Contraseña del archivo
            output_dir: Directorio de salida (opcional)
            
        Returns:
            Tuple con (éxito, mensaje)
        """
        try:
            zip_path = Path(zip_path)
            if not zip_path.exists():
                raise FileNotFoundError(f"El archivo {zip_path} no existe")
                
            if output_dir is None:
                output_dir = zip_path.parent
            else:
                output_dir = Path(output_dir)
                if not output_dir.exists():
                    output_dir.mkdir(parents=True)
            
            seven_zip_path = find_7zip_path()
            if not seven_zip_path:
                raise FileNotFoundError("No se encontró la instalación de 7-Zip")
                
            extract_cmd = [
                str(seven_zip_path / "7z.exe"),
                "x",
                str(zip_path),
                f"-p{password}",
                f"-o{output_dir}"
            ]
            
            logger.info(f"Desencriptando archivo: {zip_path}")
            
            # No mostrar la contraseña en los logs
            safe_cmd = ' '.join(extract_cmd).replace(password, "********")
            
            process = subprocess.run(
                extract_cmd, 
                shell=False, 
                capture_output=True, 
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                logger.error(f"Error al desencriptar: {process.stderr}")
                raise subprocess.CalledProcessError(process.returncode, safe_cmd)
                
            logger.info(f"Archivo desencriptado exitosamente en {output_dir}")
            return True, f"Archivo desencriptado exitosamente en {output_dir}"
        except Exception as e:
            error_msg = f"Error al desencriptar archivo: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_backup_history(self, backup_dir: str) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de respaldos realizados.
        
        Args:
            backup_dir: Directorio de respaldos
            
        Returns:
            Lista de diccionarios con información de los respaldos
        """
        backup_history = []
        
        try:
            backup_path = Path(backup_dir)
            if not backup_path.exists():
                return backup_history
                
            # Obtener archivos de respaldo
            backup_files = [
                entry.path for entry in os.scandir(backup_dir) 
                if entry.is_file() and entry.name.endswith(".7z")
            ]
            
            if not backup_files:
                return backup_history
                
            # Ordenar por fecha de modificación (más reciente primero)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            
            # Crear lista con información de respaldos
            for file_path in backup_files:
                file_stat = os.stat(file_path)
                file_name = os.path.basename(file_path)
                
                # Extraer información del nombre del archivo
                # Formato esperado: cliente_dispositivo_backup_yyyymmddhhmm.7z
                parts = file_name.split("_")
                
                backup_info = {
                    "file_name": file_name,
                    "file_path": file_path,
                    "size": file_stat.st_size,
                    "created": datetime.datetime.fromtimestamp(file_stat.st_mtime),
                    "client": parts[0] if len(parts) > 0 else "Desconocido",
                    "device": parts[1] if len(parts) > 1 else "Desconocido"
                }
                
                backup_history.append(backup_info)
            
            return backup_history
        except Exception as e:
            logger.error(f"Error al obtener historial de respaldos: {e}")
            return backup_history
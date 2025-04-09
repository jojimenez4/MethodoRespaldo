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
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Tuple
import logging

from functions import (
    decrypt, send_email, manage_backup_limit, find_mysql_bin_path, 
    find_7zip_path, KEY, BACKUP_PASSWORD, logger
)

class BackupScheduler:
    """Gestor de programación de respaldos."""
    
    def __init__(self):
        """Inicializa el programador de respaldos."""
        self.running = True
        self.scheduled = False
        self._lock = threading.Lock()
        self.scheduler_thread = None
    
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
            # Limpiar programaciones anteriores
            schedule.clear()
            
            # Calcular intervalo en segundos
            interval_seconds = (hours * 3600) + (minutes * 60)
            logger.info(f"Programando respaldo cada {interval_seconds} segundos")
            
            # Programar nueva tarea
            schedule.every(interval_seconds).seconds.do(
                lambda: backup_func(*args, **kwargs)
            )
            
            # Marcar como programado
            self.scheduled = True
            
            # Iniciar hilo de programación si no está activo
            if self.scheduler_thread is None or not self.scheduler_thread.is_alive():
                self.scheduler_thread = threading.Thread(
                    target=self._run_scheduler, 
                    daemon=True
                )
                self.scheduler_thread.start()
    
    def _run_scheduler(self) -> None:
        """Ejecuta el programador de tareas en un bucle."""
        logger.info("Iniciando programador de respaldos")
        while self.running and self.scheduled:
            schedule.run_pending()
            time.sleep(1)
        logger.info("Programador de respaldos detenido")
    
    def stop(self) -> None:
        """Detiene el programador de respaldos."""
        with self._lock:
            self.running = False
            self.scheduled = False
    
    def is_scheduled(self) -> bool:
        """
        Verifica si hay respaldos programados.
        
        Returns:
            True si hay respaldos programados, False en caso contrario
        """
        with self._lock:
            return self.scheduled

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
            
            backup_file_name = f"{client}_{device}_backup_{timestamp}.sql"
            seven_zip_file_name = f"{client}_{device}_backup_{timestamp}.7z"
            
            # Detectar rutas automáticamente
            mysql_bin_path = find_mysql_bin_path()
            seven_zip_path = find_7zip_path()
            
            # Verificar que las rutas existan
            if not mysql_bin_path:
                raise FileNotFoundError("No se pudo encontrar la instalación de MySQL")
            
            if not seven_zip_path:
                raise FileNotFoundError("No se pudo encontrar la instalación de 7-Zip")

            # Comandos de backup
            backup_file_path = backup_path / backup_file_name
            seven_zip_file_path = backup_path / seven_zip_file_name
            
            # Cambiar al directorio de MySQL y ejecutar el backup
            if update_callback:
                update_callback(10, "Iniciando respaldo...")
            
            # Crear directorio temporal para respaldo si no existe
            temp_dir = Path("./temp")
            temp_dir.mkdir(exist_ok=True)
            temp_backup_path = temp_dir / backup_file_name
            
            # Usar mysqldump para crear el respaldo
            logger.info(f"Iniciando respaldo SQL en {temp_backup_path}")
            
            # Obtener datos del servidor MySQL
            database = server_data.get("database", "mysql")
            
            mysqldump_cmd = [
                str(mysql_bin_path / "mysqldump"),
                "-e", "-R",
                "-u", "root",
                f"-p{decrypted_password}",
                database,
                f"--result-file={temp_backup_path}"
            ]
            
            # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
            safe_cmd = ' '.join(mysqldump_cmd).replace(decrypted_password, "********")
            logger.info(f"Ejecutando: {safe_cmd}")
            
            process = subprocess.run(
                mysqldump_cmd, 
                shell=False, 
                capture_output=True, 
                text=True,
                check=False  # No lanzar excepción para manejarla nosotros
            )
            
            if process.returncode != 0:
                logger.error(f"Error en mysqldump: {process.stderr}")
                raise subprocess.CalledProcessError(process.returncode, safe_cmd, 
                                                  output=process.stdout, stderr=process.stderr)
            
            if update_callback:
                update_callback(50, "Comprimiendo respaldo...")
            
            # Comprimir con 7-Zip
            logger.info(f"Comprimiendo respaldo en {seven_zip_file_path}")
            compress_cmd = [
                str(seven_zip_path / "7z.exe"),
                "a",
                f"-p{BACKUP_PASSWORD}",
                str(seven_zip_file_path),
                str(temp_backup_path)
            ]
            
            # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
            safe_compress_cmd = ' '.join(compress_cmd).replace(BACKUP_PASSWORD, "********")
            logger.info(f"Ejecutando: {safe_compress_cmd}")
            
            seven_zip_process = subprocess.run(
                compress_cmd, 
                shell=False, 
                capture_output=True, 
                text=True,
                check=False  # No lanzar excepción para manejarla nosotros
            )
            
            if seven_zip_process.returncode != 0:
                logger.error(f"Error en 7-Zip: {seven_zip_process.stderr}")
                raise subprocess.CalledProcessError(seven_zip_process.returncode, safe_compress_cmd, 
                                                  output=seven_zip_process.stdout, stderr=seven_zip_process.stderr)
            
            if update_callback:
                update_callback(70, "Eliminando archivo temporal...")
            
            # Eliminar archivo temporal
            temp_backup_path.unlink()
            
            if update_callback:
                update_callback(100, "Respaldo completado.")
            
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
            raise
    
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
            logger.debug(f"Ejecutando: {safe_cmd}")
            
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
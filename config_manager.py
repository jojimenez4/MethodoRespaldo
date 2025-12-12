"""
Módulo para gestionar la configuración de la aplicación.
Proporciona acceso centralizado a las configuraciones y estados guardados.
"""

import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set
from contextlib import contextmanager

# Import condicional para file locking
if os.name != 'nt':
    import fcntl
else:
    # En Windows usaremos msvcrt
    import msvcrt

# Determinar el directorio base (funciona con servicio o GUI)
def get_base_directory():
    """Obtiene el directorio base de la aplicación (funciona como servicio o ejecutable)."""
    if getattr(sys, 'frozen', False):
        # Ejecutando como ejecutable compilado
        return os.path.dirname(sys.executable)
    else:
        # Ejecutando como script
        return os.path.dirname(os.path.abspath(__file__))

# Directorio base fijo
APP_DIR = get_base_directory()

# Configuración de logging
logger = logging.getLogger("BackupSystem")

@contextmanager
def file_lock(filepath: str, timeout: float = 5.0):
    """
    Context manager para bloqueo de archivos multiplataforma.
    
    Args:
        filepath: Ruta del archivo a bloquear
        timeout: Tiempo máximo de espera en segundos
    
    Yields:
        File handle bloqueado
    """
    lock_path = filepath + ".lock"
    lock_file = None
    start_time = time.time()
    
    try:
        while True:
            try:
                # Intentar crear el archivo de bloqueo
                lock_file = open(lock_path, 'x')
                break
            except FileExistsError:
                # El archivo ya existe, esperar
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"No se pudo adquirir el bloqueo para {filepath} después de {timeout}s")
                time.sleep(0.1)
        
        yield lock_file
        
    finally:
        if lock_file:
            try:
                lock_file.close()
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception as e:
                logger.warning(f"Error al liberar el bloqueo: {e}")

def validate_json_structure(data: Any, expected_keys: Optional[set] = None) -> bool:
    """
    Valida que los datos JSON tienen la estructura esperada.
    
    Args:
        data: Datos a validar
        expected_keys: Conjunto de claves esperadas (opcional)
        
    Returns:
        True si la estructura es válida
    """
    if not isinstance(data, dict):
        return False
    
    if expected_keys and not expected_keys.issubset(data.keys()):
        return False
    
    return True

class ConfigManager:
    """Administrador centralizado de configuración con soporte thread-safe."""
    
    def __init__(self, status_file: str = "status.json", server_file: str = "server.json", servers_file: str = "servers.json"):
        """Inicializa el administrador de configuración."""
        # Rutas absolutas para archivos
        self.status_file = os.path.join(APP_DIR, status_file)
        self.server_file = os.path.join(APP_DIR, server_file)
        self.servers_file = os.path.join(APP_DIR, servers_file)
        
        # Locks para operaciones thread-safe
        self._status_lock = threading.RLock()
        self._server_lock = threading.RLock()
        self._servers_lock = threading.RLock()
        
        # Intentar crear archivos por defecto si no existen
        self._ensure_files_exist()
        
        # Cargar estados con locks
        with self._status_lock:
            self.program_state = self.load_state(self.status_file) or self._default_program_state()
        
        # Legacy: server_data se carga bajo demanda para compatibilidad con código antiguo
        with self._server_lock:
            self.server_data = {}
            # Solo cargar si existe (sin generar warnings)
            if os.path.exists(self.server_file):
                loaded = self.load_state(self.server_file)
                if loaded and isinstance(loaded, dict):
                    self.server_data = loaded
        
        # Asegurar que los estados están completos
        self._ensure_complete_state()
        
    def _ensure_files_exist(self):
        """Asegura que los archivos de configuración existan con valores predeterminados."""
        # Verificar status.json
        if not os.path.exists(self.status_file):
            logger.warning(f"Archivo {self.status_file} no encontrado, creando uno predeterminado")
            self.save_state(self.status_file, self._default_program_state())
            
        # servers.json se creará automáticamente al añadir el primer servidor
        # No crear server.json (obsoleto) para evitar warnings innecesarios
    
    def _default_program_state(self) -> Dict[str, Any]:
        """Retorna un estado predeterminado para el programa."""
        return {
            "running": False,
            "timestamp": None,
            "client": None,
            "backup_dir": None,
            "amount": 5,              # Valor predeterminado
            "progress": 0,
            "status": "idle",
            "version": "2.0",
            "scheduled": False,        # Indica si el respaldo está programado
            "backup_tasks": []         # Lista de tareas programadas
        }
    
    def _ensure_complete_state(self) -> None:
        """Asegura que el estado tenga todos los campos necesarios."""
        # Verificar el estado del programa
        default_state = self._default_program_state()
        updated = False
        
        # Verificar cada campo en el estado del programa
        for key, default_value in default_state.items():
            if key not in self.program_state:
                logger.debug(f"Campo '{key}' faltante, añadiendo: {default_value}")
                self.program_state[key] = default_value
                updated = True
        
        # Guardar el estado actualizado si hay cambios
        if updated:
            self.save_state(self.status_file, self.program_state)
    
    def load_state(self, filepath: str, max_retries: int = 3) -> Optional[Any]:
        """
        Carga el estado desde un archivo JSON con manejo de errores robusto.
        
        Args:
            filepath: Ruta del archivo
            max_retries: Número máximo de reintentos
            
        Returns:
            Diccionario, lista o None si hay error
        """
        filepath_obj = Path(filepath)
        
        for attempt in range(max_retries):
            try:
                if not filepath_obj.exists():
                    logger.warning(f"Archivo {filepath} no encontrado")
                    return None
                
                # Usar file lock para lectura segura
                with file_lock(filepath, timeout=10.0):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Validar que no está vacío
                        if not content.strip():
                            logger.warning(f"Archivo {filepath} está vacío")
                            return None
                        
                        try:
                            state = json.loads(content)
                            
                            # Validar que es un diccionario o lista (para servers.json)
                            if not isinstance(state, (dict, list)):
                                logger.error(f"Archivo {filepath} no contiene un objeto JSON válido (dict o list)")
                                self._backup_corrupted_file(filepath)
                                return None
                            
                            return state
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Archivo {filepath} tiene JSON inválido: {e}")
                            
                            # Intentar recuperar desde backup
                            backup_path = filepath_obj.with_suffix(f".bak")
                            if backup_path.exists():
                                logger.debug(f"Intentando recuperar desde backup: {backup_path}")
                                try:
                                    with open(backup_path, 'r', encoding='utf-8') as bf:
                                        backup_content = bf.read()
                                        backup_state = json.loads(backup_content)
                                        if isinstance(backup_state, (dict, list)):
                                            logger.info("Recuperación desde backup exitosa")
                                            # Restaurar el backup como archivo principal
                                            import shutil
                                            shutil.copy2(backup_path, filepath)
                                            return backup_state
                                except Exception as be:
                                    logger.error(f"Error al recuperar desde backup: {be}")
                            
                            # Si no hay backup o falló, intentar reparar
                            repaired = self._try_repair_json(content)
                            if repaired:
                                logger.info(f"Archivo {filepath} reparado")
                                # Guardar el archivo reparado
                                self.save_state(filepath, repaired)
                                return repaired
                            else:
                                logger.error(f"No se pudo reparar {filepath}")
                                self._backup_corrupted_file(filepath)
                                return None
                                
            except TimeoutError as e:
                logger.warning(f"Timeout esperando lock para lectura (intento {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"No se pudo leer después de {max_retries} intentos")
                    return None
                    
            except Exception as e:
                logger.error(f"Error al cargar estado (intento {attempt + 1}/{max_retries}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    return None
        
        return None
    
    def _try_repair_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Intenta reparar un JSON corrupto."""
        try:
            # Intenta limpiar el JSON y analizarlo
            # Elimina espacios en blanco innecesarios
            content = content.strip()
            # Asegúrate de que comienza y termina con llaves
            if not content.startswith('{'): content = '{' + content
            if not content.endswith('}'): content = content + '}'
            
            # Intenta analizar el JSON reparado
            return json.loads(content)
        except:
            # Si falla, devuelve None
            return None
    
    def _backup_corrupted_file(self, filepath: str) -> None:
        """Crea una copia de seguridad de un archivo corrupto."""
        try:
            filepath_obj = Path(filepath)
            if filepath_obj.exists():
                import datetime
                timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                backup_path = filepath_obj.with_suffix(f"{filepath_obj.suffix}.{timestamp}.bak")
                
                # Copia el archivo corrupto a la copia de seguridad
                import shutil
                shutil.copy2(filepath, backup_path)
                logger.debug(f"Copia de seguridad creada en {backup_path}")
        except Exception as e:
            logger.error(f"Error al crear copia de seguridad: {e}")
    
    def save_state(self, filepath: str, state: Any, max_retries: int = 3) -> bool:
        """
        Guarda el estado en un archivo JSON de manera segura con retry logic y locks.
        
        Args:
            filepath: Ruta del archivo
            state: Estado a guardar (dict, list o cualquier tipo JSON serializable)
            max_retries: Número máximo de reintentos
            
        Returns:
            True si se guardó exitosamente
        """
        filepath_obj = Path(filepath)
        
        for attempt in range(max_retries):
            try:
                # Usar file lock para evitar race conditions
                with file_lock(filepath, timeout=10.0):
                    # Asegurar que el directorio existe
                    os.makedirs(filepath_obj.parent, exist_ok=True)
                    
                    # Validar que el estado es JSON serializable
                    try:
                        json_str = json.dumps(state, ensure_ascii=False, indent=4)
                    except (TypeError, ValueError) as e:
                        logger.error(f"Estado no es JSON serializable: {e}")
                        return False
                    
                    # Crear archivo temporal
                    temp_filepath = filepath_obj.with_suffix(f".tmp{os.getpid()}")
                    
                    # Escribir en archivo temporal
                    with open(temp_filepath, 'w', encoding='utf-8') as f:
                        f.write(json_str)
                        f.flush()
                        os.fsync(f.fileno())  # Forzar escritura al disco
                    
                    # Verificar que se escribió correctamente
                    with open(temp_filepath, 'r', encoding='utf-8') as f:
                        verify_data = json.load(f)
                        if verify_data != state:
                            raise ValueError("Verificación falló: datos no coinciden")
                    
                    # Crear backup del archivo actual si existe
                    if filepath_obj.exists():
                        backup_path = filepath_obj.with_suffix(f".bak")
                        try:
                            import shutil
                            shutil.copy2(filepath_obj, backup_path)
                        except Exception as e:
                            logger.warning(f"No se pudo crear backup: {e}")
                    
                    # Atomic rename (en Windows usamos replace)
                    if os.name == 'nt':
                        # En Windows, necesitamos eliminar el destino primero
                        if filepath_obj.exists():
                            filepath_obj.unlink()
                        temp_filepath.rename(filepath_obj)
                    else:
                        # En Unix, rename es atómico
                        temp_filepath.rename(filepath_obj)
                    
                    logger.debug(f"Estado guardado exitosamente en {filepath}")
                    return True
                    
            except TimeoutError as e:
                logger.warning(f"Timeout esperando lock (intento {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                    continue
                else:
                    logger.error(f"No se pudo guardar después de {max_retries} intentos")
                    return False
                    
            except Exception as e:
                logger.error(f"Error al guardar estado (intento {attempt + 1}/{max_retries}): {e}", exc_info=True)
                
                # Limpiar archivo temporal si existe
                temp_filepath = filepath_obj.with_suffix(f".tmp{os.getpid()}")
                if temp_filepath.exists():
                    try:
                        temp_filepath.unlink()
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    return False
        
        return False
    
    def update_program_state(self, **kwargs) -> bool:
        """
        Actualiza el estado del programa con los valores proporcionados (thread-safe).
        
        Args:
            **kwargs: Pares clave-valor para actualizar
            
        Returns:
            True si la actualización fue exitosa
        """
        with self._status_lock:
            try:
                # Recargar el estado más reciente desde el archivo
                current_state = self.load_state(self.status_file)
                if current_state:
                    self.program_state = current_state
                else:
                    logger.warning("No se pudo recargar el estado, usando el estado en memoria")
                
                # Actualizar solo las claves proporcionadas
                for key, value in kwargs.items():
                    self.program_state[key] = value
                
                # Asegurar que todos los campos estén presentes
                self._ensure_complete_state()
                
                # Guardar el estado actualizado
                result = self.save_state(self.status_file, self.program_state)
                
                if result:
                    logger.debug(f"Estado del programa actualizado: {list(kwargs.keys())}")
                
                return result
            except Exception as e:
                logger.error(f"Error al actualizar estado del programa: {e}", exc_info=True)
                return False
    
    def update_server_data(self, **kwargs) -> bool:
        """
        Actualiza los datos del servidor con los valores proporcionados (thread-safe).
        
        Args:
            **kwargs: Pares clave-valor para actualizar en los datos del servidor
            
        Returns:
            True si la actualización fue exitosa, False en caso contrario
        """
        with self._server_lock:
            try:
                # Recargar el estado más reciente desde el archivo
                current_server_data = self.load_state(self.server_file)
                if current_server_data:
                    self.server_data = current_server_data
                else:
                    logger.warning("No se pudo recargar datos del servidor, usando datos en memoria")
                
                # Actualizar solo las claves proporcionadas
                for key, value in kwargs.items():
                    self.server_data[key] = value
                
                # Guardar los datos actualizados
                result = self.save_state(self.server_file, self.server_data)
                
                if result:
                    logger.debug(f"Datos del servidor actualizados: {list(kwargs.keys())}")
                
                return result
            except Exception as e:
                logger.error(f"Error al actualizar datos del servidor: {e}", exc_info=True)
                return False
    
    def reset_program_state(self) -> bool:
        """
        Restablece el estado del programa a los valores predeterminados.
        
        Returns:
            True si el restablecimiento fue exitoso, False en caso contrario
        """
        self.program_state = self._default_program_state()
        return self.save_state(self.status_file, self.program_state)
    
    def get_program_state(self) -> Dict[str, Any]:
        """
        Obtiene una copia del estado actual del programa.
        
        Returns:
            Diccionario con el estado del programa
        """
        return self.program_state.copy()
    
    def get_server_data(self) -> Dict[str, Any]:
        """
        Obtiene una copia de los datos actuales del servidor.
        
        Returns:
            Diccionario con los datos del servidor
        """
        return self.server_data.copy()
    
    def set_backup_schedule(self, hours: int, minutes: int, enabled: bool = True) -> bool:
        """
        Configura la programación de respaldos creando una tarea de frecuencia.
        
        Args:
            hours: Horas entre respaldos
            minutes: Minutos entre respaldos
            enabled: True para activar la programación, False para desactivarla
            
        Returns:
            True si la configuración fue exitosa, False en caso contrario
        """
        logger.debug(f"Configurando respaldo programado: {hours}h:{minutes}m (enabled={enabled})")
        
        # Crear tarea de frecuencia
        task = {
            "type": "frequency",
            "hours": hours,
            "minutes": minutes,
            "enabled": enabled
        }
        
        # Reemplazar todas las tareas con esta única tarea
        return self.set_backup_tasks([task])
    
    # ========== MÉTODOS PARA SISTEMA DE TAREAS ==========
    
    def get_backup_tasks(self) -> list:
        """
        Obtiene la lista de tareas de respaldo configuradas.
        
        Returns:
            Lista de diccionarios con las tareas configuradas
        """
        tasks = self.program_state.get("backup_tasks", [])
        
        # Si no hay tareas, crear una por defecto
        if not tasks and self.program_state.get("scheduled", False):
            # Crear tarea de frecuencia por defecto
            default_task = {
                "type": "frequency",
                "hours": 4,
                "minutes": 0,
                "enabled": True
            }
            tasks = [default_task]
            logger.info("Creada tarea de frecuencia por defecto: 4h:0m")
        
        return tasks
    
    def set_backup_tasks(self, tasks: list) -> bool:
        """
        Establece la lista completa de tareas de respaldo.
        
        Args:
            tasks: Lista de diccionarios con las tareas
                   Cada tarea debe tener:
                   - type: "frequency" o "fixed_time"
                   - Para frequency: hours, minutes
                   - Para fixed_time: hour, minute
                   - enabled: True/False
        
        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        # Validar tareas
        validated_tasks = []
        for task in tasks[:3]:  # Máximo 3 tareas
            if not isinstance(task, dict):
                continue
                
            task_type = task.get("type")
            if task_type == "frequency":
                validated_task = {
                    "type": "frequency",
                    "hours": int(task.get("hours", 0)),
                    "minutes": int(task.get("minutes", 0)),
                    "enabled": bool(task.get("enabled", True))
                }
                # Validar que tenga al menos algún intervalo
                if validated_task["hours"] > 0 or validated_task["minutes"] > 0:
                    validated_tasks.append(validated_task)
                    
            elif task_type == "fixed_time":
                validated_task = {
                    "type": "fixed_time",
                    "hour": int(task.get("hour", 0)) % 24,
                    "minute": int(task.get("minute", 0)) % 60,
                    "enabled": bool(task.get("enabled", True))
                }
                validated_tasks.append(validated_task)
        
        # Verificar si hay tareas habilitadas
        has_enabled = any(t.get("enabled", True) for t in validated_tasks)
        
        logger.info(f"Guardando {len(validated_tasks)} tarea(s) de respaldo")
        return self.update_program_state(
            backup_tasks=validated_tasks,
            scheduled=has_enabled and len(validated_tasks) > 0
        )
    
    def add_backup_task(self, task: dict) -> bool:
        """
        Añade una nueva tarea de respaldo.
        
        Args:
            task: Diccionario con la configuración de la tarea
        
        Returns:
            True si se añadió correctamente, False si ya hay 3 tareas
        """
        tasks = self.get_backup_tasks()
        if len(tasks) >= 3:
            logger.warning("No se puede añadir más tareas: límite de 3 alcanzado")
            return False
        
        tasks.append(task)
        return self.set_backup_tasks(tasks)
    
    def remove_backup_task(self, index: int) -> bool:
        """
        Elimina una tarea de respaldo por su índice.
        
        Args:
            index: Índice de la tarea a eliminar (0-2)
        
        Returns:
            True si se eliminó correctamente
        """
        tasks = self.get_backup_tasks()
        if 0 <= index < len(tasks):
            removed = tasks.pop(index)
            logger.info(f"Tarea eliminada: {removed}")
            return self.set_backup_tasks(tasks)
        return False
    
    def toggle_backup_task(self, index: int, enabled: bool) -> bool:
        """
        Activa o desactiva una tarea de respaldo.
        
        Args:
            index: Índice de la tarea
            enabled: True para activar, False para desactivar
        
        Returns:
            True si se actualizó correctamente
        """
        tasks = self.get_backup_tasks()
        if 0 <= index < len(tasks):
            tasks[index]["enabled"] = enabled
            return self.set_backup_tasks(tasks)
        return False
    
    def force_save_all(self) -> bool:
        """
        Fuerza el guardado completo del estado actual en el archivo.
        """
        logger.debug("Forzando guardado completo del estado")
        
        # Asegurar que todos los campos necesarios existan
        self._ensure_complete_state()
        
        # Guardar estado completo
        return self.save_state(self.status_file, self.program_state)
    
    # Añadir esta función a la clase ConfigManager en config_manager.py

    def repair_state_file(self) -> bool:
        """
        Repara el archivo de estado para asegurar que contiene todos los campos necesarios.
        """
        try:
            logger.debug("Iniciando reparación del archivo de estado")
            
            # Cargar el estado actual desde el archivo
            current_state = None
            if os.path.exists(self.status_file):
                try:
                    with open(self.status_file, 'r', encoding='utf-8') as f:
                        current_state = json.load(f)
                except Exception as e:
                    logger.error(f"Error al leer archivo de estado: {e}")
                    current_state = None
            
            # Si no hay estado o está vacío, usar el predeterminado
            if not current_state:
                current_state = self._default_program_state()
            
            # Asegurar que todos los campos necesarios existan
            default_state = self._default_program_state()
            for key, default_value in default_state.items():
                if key not in current_state:
                    current_state[key] = default_value
            
            # Guardar el estado reparado directamente en el archivo
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, ensure_ascii=False, indent=4)
            
            # Actualizar el estado en memoria
            self.program_state = current_state
            
            logger.info("Reparación completada")
            return True
        except Exception as e:
            logger.error(f"Error durante la reparación del archivo de estado: {e}", exc_info=True)
            return False
    
    # ========== MÉTODOS PARA MÚLTIPLES SERVIDORES ==========
    
    def get_servers(self) -> list:
        """
        Obtiene la lista de todos los servidores configurados.
        
        Returns:
            Lista de diccionarios con configuraciones de servidores
        """
        with self._servers_lock:
            # Si existe servers.json, usarlo
            if os.path.exists(self.servers_file):
                servers = self.load_state(self.servers_file)
                if isinstance(servers, list):
                    return servers
            
            # Migración: Si existe server.json (singular) pero no servers.json
            if os.path.exists(self.server_file):
                single_server = self.load_state(self.server_file)
                if single_server and isinstance(single_server, dict):
                    # Convertir a formato de array
                    migrated_server = {
                        "id": "server_1",
                        "name": single_server.get("client", "Servidor Principal"),
                        "enabled": True,
                        **single_server
                    }
                    servers = [migrated_server]
                    # Guardar en el nuevo formato
                    self.save_state(self.servers_file, servers)
                    logger.info("Migración automática: server.json → servers.json")
                    return servers
            
            # Si no hay nada, retornar lista vacía
            return []
    
    def get_enabled_servers(self) -> list:
        """
        Obtiene solo los servidores habilitados.
        
        Returns:
            Lista de servidores con enabled=True
        """
        all_servers = self.get_servers()
        return [s for s in all_servers if s.get("enabled", True)]
    
    def add_server(self, server_config: Dict[str, Any]) -> bool:
        """
        Añade un nuevo servidor a la configuración.
        
        Args:
            server_config: Diccionario con la configuración del servidor
            
        Returns:
            True si se añadió correctamente
        """
        with self._servers_lock:
            servers = self.get_servers()
            
            # Generar ID único
            if "id" not in server_config:
                existing_ids = [s.get("id", "") for s in servers]
                counter = 1
                while f"server_{counter}" in existing_ids:
                    counter += 1
                server_config["id"] = f"server_{counter}"
            
            # Añadir enabled por defecto
            if "enabled" not in server_config:
                server_config["enabled"] = True
            
            servers.append(server_config)
            self.save_state(self.servers_file, servers)
            logger.info(f"Servidor añadido: {server_config.get('name', server_config['id'])}")
            return True
    
    def update_server(self, server_id: str, updates: Dict[str, Any]) -> bool:
        """
        Actualiza la configuración de un servidor existente.
        
        Args:
            server_id: ID del servidor a actualizar
            updates: Diccionario con los campos a actualizar
            
        Returns:
            True si se actualizó correctamente
        """
        with self._servers_lock:
            servers = self.get_servers()
            
            for server in servers:
                if server.get("id") == server_id:
                    server.update(updates)
                    self.save_state(self.servers_file, servers)
                    logger.info(f"Servidor actualizado: {server_id}")
                    return True
            
            logger.warning(f"Servidor no encontrado: {server_id}")
            return False
    
    def delete_server(self, server_id: str) -> bool:
        """
        Elimina un servidor de la configuración.
        
        Args:
            server_id: ID del servidor a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        with self._servers_lock:
            servers = self.get_servers()
            original_count = len(servers)
            
            servers = [s for s in servers if s.get("id") != server_id]
            
            if len(servers) < original_count:
                self.save_state(self.servers_file, servers)
                logger.info(f"Servidor eliminado: {server_id}")
                return True
            
            logger.warning(f"Servidor no encontrado: {server_id}")
            return False
    
    def clear_all_servers(self) -> bool:
        """
        Elimina todos los servidores de la configuración.
        
        Returns:
            True si se eliminaron correctamente
        """
        with self._servers_lock:
            self.save_state(self.servers_file, [])
            logger.info("Todos los servidores eliminados")
            return True
    
    def toggle_server(self, server_id: str) -> bool:
        """
        Habilita/deshabilita un servidor.
        
        Args:
            server_id: ID del servidor
            
        Returns:
            True si se cambió el estado
        """
        with self._servers_lock:
            servers = self.get_servers()
            
            for server in servers:
                if server.get("id") == server_id:
                    server["enabled"] = not server.get("enabled", True)
                    self.save_state(self.servers_file, servers)
                    status = "habilitado" if server["enabled"] else "deshabilitado"
                    logger.info(f"Servidor {server_id} {status}")
                    return True
            
            return False
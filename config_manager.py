"""
Módulo para gestionar la configuración de la aplicación.
Proporciona acceso centralizado a las configuraciones y estados guardados.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

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
logger = logging.getLogger("BackupSystem.ConfigManager")

class ConfigManager:
    """Administrador centralizado de configuración."""
    
    def __init__(self, status_file: str = "status.json", server_file: str = "server.json"):
        """Inicializa el administrador de configuración."""
        # Rutas absolutas para archivos
        self.status_file = os.path.join(APP_DIR, status_file)
        self.server_file = os.path.join(APP_DIR, server_file)
        
        logger.info(f"Usando archivos de configuración: {self.status_file}, {self.server_file}")
        
        # Intentar crear archivos por defecto si no existen
        self._ensure_files_exist()
        
        # Cargar estados
        self.program_state = self.load_state(self.status_file) or self._default_program_state()
        self.server_data = self.load_state(self.server_file) or {}
        
        # Asegurar que los estados están completos
        self._ensure_complete_state()
        
    def _ensure_files_exist(self):
        """Asegura que los archivos de configuración existan con valores predeterminados."""
        # Verificar status.json
        if not os.path.exists(self.status_file):
            logger.warning(f"Archivo {self.status_file} no encontrado, creando uno predeterminado")
            self.save_state(self.status_file, self._default_program_state())
            
        # Verificar server.json
        if not os.path.exists(self.server_file):
            logger.warning(f"Archivo {self.server_file} no encontrado, creando uno predeterminado")
            self.save_state(self.server_file, {})
    
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
            "version": "1.0",
            "backup_hours": 4,         # Respaldo cada 4 horas por defecto
            "backup_minutes": 0,
            "scheduled": False         # Indica si el respaldo está programado
        }
    
    def _ensure_complete_state(self) -> None:
        """Asegura que el estado tenga todos los campos necesarios."""
        # Verificar el estado del programa
        default_state = self._default_program_state()
        updated = False
        
        # Verificar cada campo en el estado del programa
        for key, default_value in default_state.items():
            if key not in self.program_state:
                logger.info(f"Campo '{key}' faltante en el estado, añadiendo valor predeterminado: {default_value}")
                self.program_state[key] = default_value
                updated = True
        
        # Guardar el estado actualizado si hay cambios
        if updated:
            self.save_state(self.status_file, self.program_state)
            logger.info("Estado del programa actualizado con campos faltantes")
    
    def load_state(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Carga el estado desde un archivo JSON con manejo de errores."""
        try:
            if not os.path.exists(filepath):
                logger.warning(f"Archivo {filepath} no encontrado")
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    state = json.load(f)
                    logger.debug(f"Estado cargado desde {filepath}: {state}")
                    return state
                except json.JSONDecodeError:
                    logger.error(f"Archivo {filepath} está corrupto, intentando reparar")
                    # Intentar leer el archivo como texto y repararlo
                    f.seek(0)
                    content = f.read()
                    # Intentar eliminar caracteres no válidos y analizar nuevamente
                    repaired = self._try_repair_json(content)
                    if repaired:
                        logger.info(f"Archivo {filepath} reparado exitosamente")
                        return repaired
                    else:
                        logger.error(f"No se pudo reparar {filepath}, creando copia de seguridad")
                        self._backup_corrupted_file(filepath)
                        return None
        except Exception as e:
            logger.error(f"Error al cargar estado desde {filepath}: {e}")
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
                logger.info(f"Copia de seguridad creada en {backup_path}")
        except Exception as e:
            logger.error(f"Error al crear copia de seguridad: {e}")
    
    def save_state(self, filepath: str, state: Dict[str, Any]) -> bool:
        """Guarda el estado en un archivo JSON de manera segura."""
        try:
            # Importar os aquí para asegurar que está disponible
            import os
            
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Crear un archivo temporal primero
            filepath_obj = Path(filepath)
            temp_filepath = filepath_obj.with_suffix(f"{filepath_obj.suffix}.tmp")
            
            # Guardar en el archivo temporal
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
            
            # Reemplazar el archivo original
            if filepath_obj.exists():
                # En Windows, a veces no podemos simplemente renombrar sobre un archivo existente
                try:
                    filepath_obj.unlink()
                except:
                    # Si no podemos eliminar, intentar con otro enfoque
                    import os
                    os.replace(temp_filepath, filepath_obj)
                    return True
            
            # Renombrar el archivo temporal
            temp_filepath.rename(filepath_obj)
            logger.debug(f"Estado guardado en {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error al guardar el estado en {filepath}: {e}", exc_info=True)
            return False
    
    def update_program_state(self, **kwargs) -> bool:
        """Actualiza el estado del programa con los valores proporcionados."""
        try:
            # Actualizar solo las claves proporcionadas
            for key, value in kwargs.items():
                self.program_state[key] = value
                logger.debug(f"Campo '{key}' actualizado a: {value}")
            
            # Asegurar que todos los campos estén presentes
            self._ensure_complete_state()
            
            # Guardar el estado actualizado
            result = self.save_state(self.status_file, self.program_state)
            if result:
                logger.debug(f"Estado del programa actualizado con éxito")
                
            return result
        except Exception as e:
            logger.error(f"Error al actualizar estado del programa: {e}", exc_info=True)
            return False
    
    def update_server_data(self, **kwargs) -> bool:
        """
        Actualiza los datos del servidor con los valores proporcionados.
        
        Args:
            **kwargs: Pares clave-valor para actualizar en los datos del servidor
            
        Returns:
            True si la actualización fue exitosa, False en caso contrario
        """
        try:
            # Primero cargar el estado más reciente desde el archivo
            current_server_data = self.load_state(self.server_file)
            if current_server_data:
                # Actualizar con los datos más recientes
                self.server_data = current_server_data
            
            # Actualizar solo las claves proporcionadas
            for key, value in kwargs.items():
                self.server_data[key] = value
            
            # Guardar los datos actualizados
            result = self.save_state(self.server_file, self.server_data)
            if result:
                logger.debug(f"Datos del servidor actualizados: {kwargs}")
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
        Configura la programación de respaldos.
        
        Args:
            hours: Horas entre respaldos
            minutes: Minutos entre respaldos
            enabled: True para activar la programación, False para desactivarla
            
        Returns:
            True si la configuración fue exitosa, False en caso contrario
        """
        logger.info(f"Configurando respaldo programado: {hours}h:{minutes}m (enabled={enabled})")
        return self.update_program_state(
            backup_hours=hours,
            backup_minutes=minutes,
            scheduled=enabled
        )
    
    def force_save_all(self) -> bool:
        """
        Fuerza el guardado completo del estado actual en el archivo.
        Útil para asegurar que todos los campos estén presentes.
        
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        logger.info(f"Forzando guardado completo del estado: {self.program_state}")
        
        # Asegurar que todos los campos necesarios existan
        self._ensure_complete_state()
        
        # Guardar estado completo
        return self.save_state(self.status_file, self.program_state)
    
    # Añadir esta función a la clase ConfigManager en config_manager.py

    def repair_state_file(self) -> bool:
        """
        Repara el archivo de estado para asegurar que contiene todos los campos necesarios.
        Lee el archivo directamente, lo repara y lo vuelve a escribir.
        
        Returns:
            True si la reparación fue exitosa, False en caso contrario
        """
        try:
            logger.info("Iniciando reparación del archivo de estado...")
            
            # Cargar el estado actual desde el archivo
            current_state = None
            if os.path.exists(self.status_file):
                try:
                    with open(self.status_file, 'r', encoding='utf-8') as f:
                        current_state = json.load(f)
                    logger.info(f"Estado actual cargado: {current_state}")
                except Exception as e:
                    logger.error(f"Error al leer archivo de estado: {e}")
                    current_state = None
            
            # Si no hay estado o está vacío, usar el predeterminado
            if not current_state:
                current_state = self._default_program_state()
                logger.info("Usando estado predeterminado para reparación")
            
            # Asegurar que todos los campos necesarios existan
            default_state = self._default_program_state()
            for key, default_value in default_state.items():
                if key not in current_state:
                    logger.info(f"Reparando: Campo '{key}' faltante, añadiendo valor predeterminado: {default_value}")
                    current_state[key] = default_value
            
            # Guardar el estado reparado directamente en el archivo
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, ensure_ascii=False, indent=4)
            
            # Actualizar el estado en memoria
            self.program_state = current_state
            
            logger.info(f"Reparación completada. Estado actualizado: {current_state}")
            return True
        except Exception as e:
            logger.error(f"Error durante la reparación del archivo de estado: {e}", exc_info=True)
            return False
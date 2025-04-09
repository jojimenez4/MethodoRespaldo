"""
Módulo para gestionar la configuración de la aplicación.
Proporciona acceso centralizado a las configuraciones y estados guardados.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Configuración de logging
logger = logging.getLogger(__name__)

class ConfigManager:
    """Administrador centralizado de configuración."""
    
    def __init__(self, status_file: str = "status.json", server_file: str = "server.json"):
        """
        Inicializa el administrador de configuración.
        
        Args:
            status_file: Nombre del archivo de estado del programa
            server_file: Nombre del archivo de datos del servidor
        """
        self.status_file = status_file
        self.server_file = server_file
        self.program_state = self.load_state(status_file) or self._default_program_state()
        self.server_data = self.load_state(server_file) or {}
        
    def _default_program_state(self) -> Dict[str, Any]:
        """
        Retorna un estado predeterminado para el programa.
        
        Returns:
            Diccionario con valores predeterminados
        """
        return {
            "running": False,
            "timestamp": None,
            "client": None,
            "backup_dir": None,
            "amount": 5,  # Valor predeterminado
            "progress": 0,
            "status": "idle",
            "version": "1.1.0"
        }
    
    def load_state(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Carga el estado desde un archivo JSON con manejo de errores.
        
        Args:
            filepath: Ruta del archivo a cargar
            
        Returns:
            Diccionario con el estado o None si hay error
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            logger.debug(f"Estado cargado desde {filepath}")
            return state
        except FileNotFoundError:
            logger.warning(f"Archivo {filepath} no encontrado, se creará uno nuevo")
            return None
        except json.JSONDecodeError:
            logger.error(f"Archivo {filepath} está corrupto, se creará uno nuevo")
            # Hacer backup del archivo corrupto
            filepath_obj = Path(filepath)
            if filepath_obj.exists():
                backup_path = filepath_obj.with_suffix(filepath_obj.suffix + ".corrupto")
                filepath_obj.rename(backup_path)
                logger.info(f"Se ha guardado una copia del archivo corrupto en {backup_path}")
            return None
        except Exception as e:
            logger.error(f"Error al cargar estado desde {filepath}: {e}")
            return None
    
    def save_state(self, filepath: str, state: Dict[str, Any]) -> bool:
        """
        Guarda el estado en un archivo JSON de manera segura.
        
        Args:
            filepath: Ruta del archivo
            state: Diccionario con el estado a guardar
            
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        try:
            # Crear un archivo temporal primero
            filepath = Path(filepath)
            temp_filepath = filepath.with_suffix(filepath.suffix + ".tmp")
            
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
            
            # Reemplazar el archivo original solo si la escritura temporal fue exitosa
            if filepath.exists():
                filepath.unlink()  # Eliminar el original primero para evitar problemas en Windows
            
            temp_filepath.rename(filepath)
            logger.debug(f"Estado guardado en {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error al guardar el estado en {filepath}: {e}")
            return False
    
    def update_program_state(self, **kwargs) -> bool:
        """
        Actualiza el estado del programa con los valores proporcionados.
        
        Args:
            **kwargs: Pares clave-valor para actualizar en el estado
            
        Returns:
            True si la actualización fue exitosa, False en caso contrario
        """
        # Actualizar solo las claves proporcionadas
        for key, value in kwargs.items():
            self.program_state[key] = value
        
        # Guardar el estado actualizado
        result = self.save_state(self.status_file, self.program_state)
        if result:
            logger.debug(f"Estado del programa actualizado: {kwargs}")
        return result
    
    def update_server_data(self, **kwargs) -> bool:
        """
        Actualiza los datos del servidor con los valores proporcionados.
        
        Args:
            **kwargs: Pares clave-valor para actualizar en los datos del servidor
            
        Returns:
            True si la actualización fue exitosa, False en caso contrario
        """
        # Actualizar solo las claves proporcionadas
        for key, value in kwargs.items():
            self.server_data[key] = value
        
        # Guardar los datos actualizados
        result = self.save_state(self.server_file, self.server_data)
        if result:
            logger.debug(f"Datos del servidor actualizados: {kwargs}")
        return result
    
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
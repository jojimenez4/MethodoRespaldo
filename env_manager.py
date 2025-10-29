"""
Módulo para gestión segura de variables de entorno
Las variables se embeben en el código durante la compilación
NO se expone el archivo .env en la distribución
"""

import os
import sys
from pathlib import Path

# Variables de entorno embebidas (serán reemplazadas durante build)
EMBEDDED_ENV = {
    # PLACEHOLDER: Este diccionario será reemplazado por build.py con valores reales
    # NO editar manualmente - se genera automáticamente
}

class EnvManager:
    """Gestor de variables de entorno con fallback a .env para desarrollo"""
    
    _initialized = False
    _env_vars = {}
    
    @classmethod
    def initialize(cls):
        """Inicializa el gestor de variables de entorno"""
        if cls._initialized:
            return
        
        # Prioridad 1: Variables embebidas (producción compilada)
        if EMBEDDED_ENV and len(EMBEDDED_ENV) > 1:  # Más de un placeholder
            cls._env_vars = EMBEDDED_ENV.copy()
            cls._initialized = True
            return
        
        # Prioridad 2: Archivo .env (desarrollo)
        env_file = Path('.env')
        if env_file.exists():
            cls._load_from_file(env_file)
        else:
            # Buscar .env en el directorio del ejecutable
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
                env_file = exe_dir / '.env'
                if env_file.exists():
                    cls._load_from_file(env_file)
        
        cls._initialized = True
    
    @classmethod
    def _load_from_file(cls, env_file: Path):
        """Carga variables desde archivo .env"""
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Ignorar comentarios y líneas vacías
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            cls._env_vars[key] = value
        except Exception as e:
            print(f"Advertencia: Error leyendo .env: {e}")
    
    @classmethod
    def get(cls, key: str, default: str = None) -> str:
        """
        Obtiene una variable de entorno
        
        Args:
            key: Nombre de la variable
            default: Valor por defecto si no existe
        
        Returns:
            Valor de la variable o default
        """
        if not cls._initialized:
            cls.initialize()
        
        # Prioridad: variables embebidas > variables de sistema > default
        value = cls._env_vars.get(key)
        if value is None:
            value = os.environ.get(key, default)
        
        return value
    
    @classmethod
    def get_all(cls) -> dict:
        """
        Obtiene todas las variables de entorno cargadas
        
        Returns:
            Diccionario con todas las variables
        """
        if not cls._initialized:
            cls.initialize()
        
        return cls._env_vars.copy()
    
    @classmethod
    def is_embedded(cls) -> bool:
        """
        Verifica si las variables están embebidas (compilación)
        
        Returns:
            True si está usando variables embebidas, False si usa .env
        """
        return EMBEDDED_ENV and len(EMBEDDED_ENV) > 1


# Inicializar automáticamente al importar
EnvManager.initialize()


# Funciones de conveniencia (compatibles con python-dotenv)
def load_dotenv():
    """Carga variables de entorno (compatibilidad con dotenv)"""
    EnvManager.initialize()


def get_env(key: str, default: str = None) -> str:
    """
    Obtiene variable de entorno
    
    Args:
        key: Nombre de la variable
        default: Valor por defecto
    
    Returns:
        Valor de la variable
    """
    return EnvManager.get(key, default)


# Alias para compatibilidad
getenv = get_env

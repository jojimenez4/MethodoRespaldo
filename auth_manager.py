"""
Módulo para gestionar la autenticación de usuarios.
Proporciona funciones para verificar credenciales y administrar permisos.
"""

import os
import json
import logging
import hashlib
import base64
import secrets
import string
from typing import Dict, Any, Tuple, Optional, List

# Obtener la ruta absoluta del directorio de la aplicación
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de logging
logger = logging.getLogger("BackupSystem")

class AuthManager:
    """Administrador de autenticación de usuarios."""
    
    def __init__(self, users_file: str = "users.json"):
        """
        Inicializa el administrador de autenticación.
        
        Args:
            users_file: Nombre del archivo de usuarios
        """
        # Usar ruta absoluta para archivo de usuarios
        self.users_file = os.path.join(APP_DIR, users_file)
        self.users = self._load_users()
        
        # Crear usuarios predeterminados si no existen
        if not self.users:
            self._create_default_users()
            
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """
        Carga los usuarios desde el archivo JSON.
        
        Returns:
            Diccionario con información de usuarios
        """
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error al cargar usuarios: {e}")
            return {}
    
    def _save_users(self) -> bool:
        """
        Guarda los usuarios en el archivo JSON.
        
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        try:
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error al guardar usuarios: {e}")
            return False
    
    def _create_default_users(self) -> None:
        """Crea los usuarios predeterminados del sistema."""
        default_users = {
            "vpacheco": {"password_hash": self._hash_password("24zA0Sog"), "role": "admin"},
            "eloyola": {"password_hash": self._hash_password("d99B3Kdy"), "role": "admin"},
            "mquezada": {"password_hash": self._hash_password("vAZ865bW"), "role": "admin"},
            "asoto": {"password_hash": self._hash_password("W2s3Q1GL"), "role": "admin"},
            "earancibia": {"password_hash": self._hash_password("Tg9g1Q4p"), "role": "admin"},
            "csegovia": {"password_hash": self._hash_password("e0N20jvZ"), "role": "admin"},
            "smellado": {"password_hash": self._hash_password("e9Oy1n7X"), "role": "admin"},
            "agarcia": {"password_hash": self._hash_password("Vh33c0B2"), "role": "admin"},
            "jjimenez": {"password_hash": self._hash_password("70HfLi46"), "role": "admin"},
            "erodriguez": {"password_hash": self._hash_password("93Glzeg4"), "role": "admin"},
            "rrodriguez": {"password_hash": self._hash_password("D71q2As9"), "role": "admin"},
            "wnegrete": {"password_hash": self._hash_password("0N9g6o1y"), "role": "admin"},
            "samir": {"password_hash": self._hash_password("8xW97EeV"), "role": "admin"}
        }
        
        self.users = default_users
        self._save_users()
        logger.info(f"Usuarios predeterminados creados")
    
    def _hash_password(self, password: str) -> str:
        """
        Genera un hash seguro para una contraseña.
        
        Args:
            password: Contraseña a hashear
            
        Returns:
            Hash de la contraseña en formato base64
        """
        # Usamos SHA-256 para el hash (en producción sería mejor usar bcrypt)
        hash_obj = hashlib.sha256(password.encode('utf-8'))
        return base64.b64encode(hash_obj.digest()).decode('utf-8')
    
    def verify_credentials(self, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verifica las credenciales de un usuario.
        
        Args:
            username: Nombre de usuario
            password: Contraseña
            
        Returns:
            Tupla con (éxito_autenticación, datos_usuario o None)
        """
        if username not in self.users:
            logger.warning(f"Intento de acceso con usuario inexistente: {username}")
            return False, None
        
        user_data = self.users[username]
        password_hash = self._hash_password(password)
        
        if password_hash == user_data["password_hash"]:
            logger.info(f"Acceso exitoso: usuario {username}")
            return True, user_data
        else:
            logger.warning(f"Acceso fallido: contraseña incorrecta para {username}")
            return False, None
    
    def change_password(self, username: str, new_password: str) -> bool:
        """
        Cambia la contraseña de un usuario.
        
        Args:
            username: Nombre de usuario
            new_password: Nueva contraseña
            
        Returns:
            True si el cambio fue exitoso, False en caso contrario
        """
        if username not in self.users:
            logger.error(f"No se puede cambiar contraseña para usuario inexistente: {username}")
            return False
        
        try:
            self.users[username]["password_hash"] = self._hash_password(new_password)
            return self._save_users()
        except Exception as e:
            logger.error(f"Error al cambiar contraseña: {e}")
            return False
    
    def add_user(self, username: str, password: str, role: str = "user") -> bool:
        """
        Añade un nuevo usuario.
        
        Args:
            username: Nombre de usuario
            password: Contraseña
            role: Rol del usuario
            
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        if username in self.users:
            logger.warning(f"El usuario {username} ya existe")
            return False
        
        try:
            self.users[username] = {
                "password_hash": self._hash_password(password),
                "role": role
            }
            return self._save_users()
        except Exception as e:
            logger.error(f"Error al añadir usuario: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """
        Elimina un usuario.
        
        Args:
            username: Nombre de usuario
            
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        if username not in self.users:
            logger.warning(f"No se puede eliminar usuario inexistente: {username}")
            return False
        
        try:
            del self.users[username]
            return self._save_users()
        except Exception as e:
            logger.error(f"Error al eliminar usuario: {e}")
            return False
    
    def get_users(self) -> List[str]:
        """
        Obtiene la lista de nombres de usuario.
        
        Returns:
            Lista de nombres de usuario
        """
        return list(self.users.keys())
    
    def reset_password(self, username: str) -> Optional[str]:
        """
        Restablece la contraseña de un usuario a una aleatoria.
        
        Args:
            username: Nombre de usuario
            
        Returns:
            Nueva contraseña o None si falló
        """
        if username not in self.users:
            logger.warning(f"No se puede restablecer contraseña para usuario inexistente: {username}")
            return None
        
        try:
            # Generar contraseña aleatoria
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            
            # Actualizar contraseña
            self.users[username]["password_hash"] = self._hash_password(new_password)
            if self._save_users():
                return new_password
            return None
        except Exception as e:
            logger.error(f"Error al restablecer contraseña: {e}")
            return None
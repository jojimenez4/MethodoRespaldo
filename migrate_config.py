"""
Script de migración: Convierte server.json a servers.json
Este script se ejecuta automáticamente cuando existe server.json pero no servers.json
"""

import json
import os
import sys
from pathlib import Path

def get_base_directory():
    """Obtiene el directorio base de la aplicación."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def migrate_server_config():
    """
    Migra la configuración de un solo servidor (server.json) 
    al formato de múltiples servidores (servers.json)
    """
    app_dir = get_base_directory()
    server_file = os.path.join(app_dir, "server.json")
    servers_file = os.path.join(app_dir, "servers.json")
    
    # Si ya existe servers.json, no hacer nada
    if os.path.exists(servers_file):
        print("servers.json ya existe, no se requiere migración")
        return False
    
    # Si no existe server.json, no hay nada que migrar
    if not os.path.exists(server_file):
        print("No se encontró server.json para migrar")
        # Crear servers.json vacío
        with open(servers_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        print("Creado servers.json vacío")
        return True
    
    try:
        # Leer server.json
        with open(server_file, 'r', encoding='utf-8') as f:
            server_data = json.load(f)
        
        if not server_data:
            print("server.json está vacío")
            with open(servers_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            return True
        
        # Convertir a formato array
        migrated_server = {
            "id": "server_1",
            "name": server_data.get("client", "Servidor Principal"),
            "enabled": True,
            **server_data
        }
        
        servers = [migrated_server]
        
        # Guardar servers.json
        with open(servers_file, 'w', encoding='utf-8') as f:
            json.dump(servers, f, ensure_ascii=False, indent=4)
        
        print(f"✓ Migración completada: {server_file} → {servers_file}")
        print(f"  Servidor migrado: {migrated_server['name']}")
        
        # Crear backup de server.json
        backup_file = os.path.join(app_dir, "server.json.backup")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(server_data, f, ensure_ascii=False, indent=4)
        print(f"✓ Backup creado: {backup_file}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error durante la migración: {e}")
        return False

if __name__ == "__main__":
    success = migrate_server_config()
    sys.exit(0 if success else 1)

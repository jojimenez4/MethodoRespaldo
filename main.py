import logging
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
from functions import save_state, program_state, STATUS_PROGRAM, logger
from views import create_login_interface

def parse_arguments():
    """Procesa los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Sistema de respaldo de bases de datos")
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Activa el modo debug con más información en logs'
    )
    parser.add_argument(
        '--backup-now', 
        action='store_true',
        help='Ejecuta un respaldo inmediato usando la configuración guardada'
    )
    return parser.parse_args()

def ensure_directories():
    """Asegura que los directorios necesarios existan."""
    for directory in ["logs", "temp"]:
        Path(directory).mkdir(exist_ok=True)

def initialize_program_state() -> Dict[str, Any]:
    """
    Inicializa el estado del programa si no existe.
    
    Returns:
        Diccionario con el estado del programa
    """
    if not program_state:
        new_state = {
            "running": False,
            "timestamp": None,
            "client": None,
            "backup_dir": None,
            "amount": 5,  # Valor predeterminado
            "progress": 0,
            "status": "idle",
            "version": "1.0.0"
        }
        save_state(STATUS_PROGRAM, new_state)
        return new_state
    return program_state

def initialize_app():
    """Inicializa la aplicación y maneja cualquier error de inicio."""
    try:
        # Procesar argumentos
        args = parse_arguments()
        
        # Configurar nivel de log según argumentos
        if args.debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Modo debug activado")
        
        # Asegurar que los directorios necesarios existan
        ensure_directories()
        
        # Inicializar estado del programa
        state = initialize_program_state()
        
        # Si se solicita respaldo inmediato
        if args.backup_now:
            from functions import backup_mysql_database, server_data_state
            
            if state.get("backup_dir") and server_data_state.get("password"):
                logger.info("Ejecutando respaldo inmediato...")
                try:
                    backup_mysql_database(
                        server_data_state["password"],
                        state["backup_dir"],
                        server_data_state.get("client", "Cliente"),
                        state.get("amount", 5)
                    )
                    logger.info("Respaldo inmediato completado")
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"Error en respaldo inmediato: {e}")
                    sys.exit(1)
            else:
                logger.error("No hay configuración para respaldo inmediato")
                sys.exit(1)
        
        # Iniciar la interfaz de login
        create_login_interface()
    except Exception as e:
        logger.critical(f"Error fatal al iniciar la aplicación: {e}", exc_info=True)
        if program_state:
            save_state(STATUS_PROGRAM, program_state)
        sys.exit(1)

if __name__ == "__main__":
    initialize_app()
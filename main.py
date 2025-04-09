import logging
import sys
from pathlib import Path
from functions import save_state, program_state, STATUS_PROGRAM
from views import create_login_interface

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger(__name__)

def ensure_directories():
    """Asegura que los directorios necesarios existan."""
    Path("logs").mkdir(exist_ok=True)

def initialize_app():
    """Inicializa la aplicación y maneja cualquier error de inicio."""
    try:
        ensure_directories()
        
        # Inicializar estado si no existe
        global program_state
        if program_state is None:
            program_state = {
                "running": False,
                "timestamp": None,
                "client": None,
                "backup_dir": None,
                "amount": None,
                "progress": 0,
                "status": "idle"
            }
            save_state(STATUS_PROGRAM, program_state)
        
        # Iniciar la interfaz de login
        create_login_interface()
    except Exception as e:
        logger.critical(f"Error fatal al iniciar la aplicación: {e}", exc_info=True)
        if program_state:
            save_state(STATUS_PROGRAM, program_state)
        sys.exit(1)

if __name__ == "__main__":
    initialize_app()
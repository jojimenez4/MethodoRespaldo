import os
import dotenv
import socket
import subprocess
import datetime
import base64
import mysql.connector
import pyodbc
import smtplib
import json
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Hash import SHA256
from contextlib import contextmanager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
dotenv.load_dotenv()

# Constantes de configuración
KEY = os.getenv("KEY", "").encode("utf-8")
USER = os.getenv("USER")
DATABASE = os.getenv("DATABASE")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # Corregido: EMAIL_ADRESS → EMAIL_ADDRESS
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")
STATUS_PROGRAM = os.getenv("STATUS_PROGRAM", "status.json")
SERVER_DATA = os.getenv("SERVER_DATA", "server.json")

def encrypt(key, source, encode=True):
    """Encripta datos usando AES-CBC."""
    if isinstance(source, str):
        source = source.encode("utf-8")
        
    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size) 
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data

def decrypt(key, source, decode=True):
    """Desencripta datos encriptados con AES-CBC."""
    try:
        if decode:
            source = base64.b64decode(source.encode("latin-1"))
        key = SHA256.new(key).digest()
        IV = source[:AES.block_size]
        decryptor = AES.new(key, AES.MODE_CBC, IV)  
        data = decryptor.decrypt(source[AES.block_size:])
        padding = data[-1]
        if data[-padding:] != bytes([padding]) * padding:
            raise ValueError("Invalid padding...")
        return data[:-padding]
    except Exception as e:
        logger.error(f"Error al desencriptar: {e}")
        raise

@contextmanager
def mysql_connection(host, port, password):
    """Administra la conexión a MySQL de forma segura usando context manager."""
    connection = None
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=USER,
            password=decrypted_password,
            database=DATABASE
        )
        yield connection
    except mysql.connector.Error as err:
        logger.error(f"Error de conexión MySQL: {err}")
        raise
    finally:
        if connection and connection.is_connected():
            connection.close()

def bd_connect_mysql(host, port, password):
    """Prueba la conexión a MySQL y obtiene información del cliente."""
    try:
        with mysql_connection(host, port, password) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT nombre_cliente FROM conf_sistema")
                result = cursor.fetchone()
                
                if result:
                    return result[0], True
                else:
                    return "Nombre no encontrado en conf_sistema", False
    except mysql.connector.Error as err:
        logger.error(f"Error en Base de Datos: {err}")
        return f"Error en Base de Datos: {err}", False
    except Exception as e:
        logger.error(f"Un error inesperado ha ocurrido: {e}")
        return f"Un error inesperado ha ocurrido: {e}", False

def bd_server_verify_sql_server(server, username, password):
    """Verifica la conexión a SQL Server."""
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        
        with pyodbc.connect(connection_string) as connection:
            # Verificación exitosa si llegamos aquí
            return True
    except pyodbc.Error as err:
        logger.error(f"Error durante la verificación del servidor SQL Server: {err}")
        return False

def backup_mysql_database(password, backup_dir, client, amount, update_callback=None):
    """Realiza un backup de la base de datos MySQL."""
    try:
        # Validar parámetros de entrada
        backup_path = Path(backup_dir)
        if not backup_path.is_dir():
            raise ValueError(f"El directorio {backup_dir} no existe")
        
        if not client:
            raise ValueError("Se requiere un nombre de cliente válido")
        
        # Preparar nombres de archivos y rutas
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
        timestamp_email = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}"
        
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        
        # Sanitizar nombre del cliente para el archivo
        client = client.replace(" ", "_").replace("/", "_").replace("\\", "_")
        device = socket.gethostname()
        
        backup_file_name = f"{client}_{device}_backup_{timestamp}.txt"
        seven_zip_file_name = f"{client}_{device}_backup_{timestamp}.7z"
        
        mysql_bin_path = Path("C:/mysql/bin")
        seven_zip_path = Path("C:/7-Zip")
        
        # Verificar que las rutas existan
        if not mysql_bin_path.exists():
            raise FileNotFoundError(f"No se encontró la ruta de MySQL: {mysql_bin_path}")
        
        if not seven_zip_path.exists():
            raise FileNotFoundError(f"No se encontró la ruta de 7-Zip: {seven_zip_path}")

        # Comandos de backup
        backup_file_path = seven_zip_path / backup_file_name
        seven_zip_file_path = seven_zip_path / seven_zip_file_name
        final_backup_path = backup_path / seven_zip_file_name
        
        # Cambiar al directorio de MySQL y ejecutar el backup
        if update_callback:
            update_callback(10, "Iniciando respaldo...")
        
        os.chdir(mysql_bin_path)
        mysqldump_cmd = f'mysqldump -e -R -u root -p{decrypted_password} {DATABASE} > "{backup_file_path}"'
        
        process = subprocess.run(mysqldump_cmd, shell=True, capture_output=True, text=True)
        if process.returncode != 0:
            logger.error(f"Error en mysqldump: {process.stderr}")
            raise subprocess.CalledProcessError(process.returncode, mysqldump_cmd, 
                                               output=process.stdout, stderr=process.stderr)
        
        if update_callback:
            update_callback(50, "Comprimiendo respaldo...")
        
        # Comprimir con 7-Zip
        os.chdir(seven_zip_path)
        compress_cmd = f'7z.exe a -p"{BACKUP_PASSWORD}" "{seven_zip_file_path}" "{backup_file_path}"'
        
        seven_zip_process = subprocess.run(compress_cmd, shell=True, capture_output=True, text=True)
        if seven_zip_process.returncode != 0:
            logger.error(f"Error en 7-Zip: {seven_zip_process.stderr}")
            raise subprocess.CalledProcessError(seven_zip_process.returncode, compress_cmd, 
                                               output=seven_zip_process.stdout, stderr=seven_zip_process.stderr)
        
        if update_callback:
            update_callback(70, "Eliminando archivo temporal...")
        
        # Eliminar archivo temporal y mover al destino final
        backup_file_path.unlink()
        
        if update_callback:
            update_callback(90, "Moviendo respaldo a destino...")
        
        seven_zip_file_path.rename(final_backup_path)
        
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
        
        return True
        
    except Exception as e:
        error_message = f"Error en el proceso de respaldo: {e}"
        logger.error(error_message)
        send_email(client, f"Error ocurrido al respaldar datos: {e}")
        raise

def send_email(client, message):
    """Envía un correo electrónico de notificación."""
    receiver_email = "jose.jimenez@methodo.cl"
    
    # Información de configuración del correo
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    try:
        # Verificar que tengamos credenciales
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            raise ValueError("Credenciales de correo no configuradas")
            
        # Usar with para asegurar que se cierre la conexión
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            # Mejorar el formato del asunto según el contenido
            if "Error" in message:
                subject = f"[ERROR] Respaldo interrumpido - Cliente: {client}"
            else:
                subject = f"[ÉXITO] Respaldo completado - Cliente: {client}"
            
            # Crear mensaje multiparte
            email_message = MIMEMultipart()
            email_message["From"] = EMAIL_ADDRESS
            email_message["To"] = receiver_email
            email_message["Subject"] = subject
            
            # Agregar cuerpo del mensaje
            email_message.attach(MIMEText(message, "plain"))
            
            # Enviar el correo
            server.send_message(email_message)
            
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Error de autenticación al enviar correo: {e}")
        return False
    except Exception as e:
        logger.error(f"Error al enviar correo: {e}")
        return False

def manage_backup_limit(backup_dir, amount):
    """Mantiene solo el número especificado de respaldos más recientes."""
    try:
        if not amount or amount <= 0:
            return True
            
        backup_path = Path(backup_dir)
        files = list(backup_path.glob("*.7z"))
        
        # Ordenar por fecha de modificación (más reciente primero)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Eliminar archivos antiguos que exceden el límite
        if len(files) > amount:
            for file in files[amount:]:
                file.unlink()
                logger.info(f"Archivo antiguo eliminado: {file}")
                
        return True
    except Exception as e:
        logger.error(f"Error al gestionar límite de respaldos: {e}")
        return False

def save_state(filepath, state):
    """Guarda el estado del programa en un archivo JSON de manera segura."""
    try:
        # Crear un archivo temporal primero
        filepath = Path(filepath)
        temp_filepath = filepath.with_suffix(filepath.suffix + ".tmp")
        
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
        
        # Reemplazar el archivo original solo si la escritura temporal fue exitosa
        if filepath.exists():
            temp_filepath.replace(filepath)
        else:
            temp_filepath.rename(filepath)
        return True
    except Exception as e:
        logger.error(f"Error al guardar el estado: {e}")
        return False

def load_state(filepath):
    """Carga el estado del programa desde un archivo JSON con manejo de errores mejorado."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        return state
    except FileNotFoundError:
        logger.warning(f"Archivo de estado {filepath} no encontrado, se creará uno nuevo")
        return None
    except json.JSONDecodeError:
        logger.error(f"El archivo de estado {filepath} está corrupto, se creará uno nuevo")
        # Hacer backup del archivo corrupto
        filepath_obj = Path(filepath)
        if filepath_obj.exists():
            backup_path = filepath_obj.with_suffix(filepath_obj.suffix + ".corrupto")
            filepath_obj.rename(backup_path)
        return None
    except Exception as e:
        logger.error(f"Error al cargar el estado: {e}")
        return None

def decrypt_backup_file(zip_path, password, output_dir=None):
    """Desencripta un archivo de respaldo 7z"""
    try:
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"El archivo {zip_path} no existe")
            
        if output_dir is None:
            output_dir = zip_path.parent
        
        seven_zip_path = Path("C:/7-Zip")
        if not seven_zip_path.exists():
            raise FileNotFoundError("No se encontró la ruta de 7-Zip")
            
        extract_cmd = f'"{seven_zip_path}/7z.exe" x "{zip_path}" -p"{password}" -o"{output_dir}"'
        
        process = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)
        if process.returncode != 0:
            logger.error(f"Error al desencriptar: {process.stderr}")
            raise subprocess.CalledProcessError(process.returncode, extract_cmd)
            
        return True, f"Archivo desencriptado exitosamente en {output_dir}"
    except Exception as e:
        error_msg = f"Error al desencriptar archivo: {e}"
        logger.error(error_msg)
        return False, error_msg

# Inicializar estados
program_state = load_state(STATUS_PROGRAM)
server_data_state = load_state(SERVER_DATA)
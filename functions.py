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
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256, HMAC
from Crypto.Util.Padding import pad, unpad
from contextlib import contextmanager
from typing import Tuple, Dict, Any, Optional, Union, Callable, Generator

# Configurar logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    filename='app.log'
)
logger = logging.getLogger(__name__)

# Agregar manejador para consola
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)

# Cargar variables de entorno
dotenv.load_dotenv()

# Constantes de configuración
KEY = os.getenv("KEY", "").encode("utf-8")
USER = os.getenv("USER")
DATABASE = os.getenv("DATABASE")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")
STATUS_PROGRAM = os.getenv("STATUS_PROGRAM", "status.json")
SERVER_DATA = os.getenv("SERVER_DATA", "server.json")

# Verificar variables críticas
if not KEY:
    logger.warning("KEY no configurada en variables de entorno. Se generará una clave temporal.")
    KEY = get_random_bytes(32)  # Generar clave temporal para esta sesión
    
if not BACKUP_PASSWORD:
    logger.warning("BACKUP_PASSWORD no configurada. Los respaldos podrían no ser seguros.")

# Mejorar encriptación con autenticación
def encrypt(key: bytes, source: Union[str, bytes], encode: bool = True) -> Union[str, bytes]:
    """
    Encripta datos usando AES-GCM con autenticación.
    
    Args:
        key: Clave de encriptación
        source: Datos a encriptar
        encode: Si es True, codifica el resultado en base64
        
    Returns:
        Datos encriptados (codificados en base64 si encode=True)
    """
    try:
        if isinstance(source, str):
            source = source.encode("utf-8")
            
        # Generar hash de la clave para tener longitud fija
        key_hash = SHA256.new(key).digest()
        
        # Generar nonce aleatorio
        nonce = get_random_bytes(16)
        
        # Crear cifrador AES en modo GCM (más seguro que CBC)
        cipher = AES.new(key_hash, AES.MODE_GCM, nonce=nonce)
        
        # Cifrar datos
        ciphertext, tag = cipher.encrypt_and_digest(source)
        
        # Combinar nonce + tag + texto cifrado
        encrypted_data = nonce + tag + ciphertext
        
        return base64.b64encode(encrypted_data).decode("utf-8") if encode else encrypted_data
    except Exception as e:
        logger.error(f"Error de encriptación: {e}")
        raise

def decrypt(key: bytes, source: Union[str, bytes], decode: bool = True) -> bytes:
    """
    Desencripta datos encriptados con AES-GCM.
    
    Args:
        key: Clave de encriptación
        source: Datos encriptados
        decode: Si es True, decodifica primero de base64
        
    Returns:
        Datos desencriptados
    """
    try:
        # Decodificar si es necesario
        if decode:
            source = base64.b64decode(source)
            
        # Generar hash de la clave para tener longitud fija
        key_hash = SHA256.new(key).digest()
        
        # Extraer nonce, tag y texto cifrado
        nonce = source[:16]
        tag = source[16:32]
        ciphertext = source[32:]
        
        # Crear descifrador
        cipher = AES.new(key_hash, AES.MODE_GCM, nonce=nonce)
        
        # Descifrar y verificar
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        
        return plaintext
    except ValueError as ve:
        logger.error(f"Error de validación en descifrado: {ve}")
        raise ValueError("Autenticación fallida. Los datos pueden haber sido alterados.")
    except Exception as e:
        logger.error(f"Error al desencriptar: {e}")
        raise

@contextmanager
def mysql_connection(host: str, port: int, password: str) -> Generator[mysql.connector.connection.MySQLConnection, None, None]:
    """
    Administra la conexión a MySQL de forma segura usando context manager.
    
    Args:
        host: Host del servidor MySQL
        port: Puerto del servidor MySQL
        password: Contraseña encriptada
        
    Yields:
        Conexión activa a MySQL
    """
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
            logger.debug("Conexión MySQL cerrada")

def bd_connect_mysql(host: str, port: int, password: str) -> Tuple[str, bool]:
    """
    Prueba la conexión a MySQL y obtiene información del cliente.
    
    Args:
        host: Host del servidor MySQL
        port: Puerto del servidor MySQL
        password: Contraseña encriptada
        
    Returns:
        Tuple con (nombre_cliente, éxito_conexión)
    """
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
        error_msg = f"Error en Base de Datos MySQL: {err}"
        logger.error(error_msg)
        return error_msg, False
    except Exception as e:
        error_msg = f"Error inesperado en conexión MySQL: {e}"
        logger.error(error_msg)
        return error_msg, False

def bd_server_verify_sql_server(server: str, username: str, password: str) -> bool:
    """
    Verifica la conexión a SQL Server.
    
    Args:
        server: Nombre del servidor SQL Server
        username: Nombre de usuario
        password: Contraseña encriptada
        
    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        
        with pyodbc.connect(connection_string) as connection:
            # Verificación exitosa si llegamos aquí
            return True
    except pyodbc.Error as err:
        logger.error(f"Error durante la verificación del servidor SQL Server: {err}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado en verificación SQL Server: {e}")
        return False

def backup_mysql_database(
    password: str, 
    backup_dir: str, 
    client: str, 
    amount: int,
    update_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Realiza un backup de la base de datos MySQL.
    
    Args:
        password: Contraseña encriptada del servidor MySQL
        backup_dir: Directorio donde se almacenará el backup
        client: Nombre del cliente
        amount: Cantidad máxima de backups a mantener
        update_callback: Función de callback para actualizar el progreso
        
    Returns:
        True si el backup fue exitoso, False en caso contrario
    """
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
        mysqldump_cmd = [
            str(mysql_bin_path / "mysqldump"),
            "-e", "-R",
            "-u", "root",
            f"-p{decrypted_password}",
            DATABASE,
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

def find_mysql_bin_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de MySQL.
    
    Returns:
        Path a la carpeta bin de MySQL o None si no se encuentra
    """
    common_paths = [
        Path("C:/Program Files/MySQL/MySQL Server 8.0/bin"),
        Path("C:/Program Files/MySQL/MySQL Server 5.7/bin"),
        Path("C:/mysql/bin")
    ]
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "mysqldump.exe").exists():
            return path
    
    # Buscar en PATH del sistema
    try:
        result = subprocess.run(["where", "mysqldump"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            return path
    except Exception:
        pass
    
    return None

def find_7zip_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de 7-Zip.
    
    Returns:
        Path a la carpeta de 7-Zip o None si no se encuentra
    """
    common_paths = [
        Path("C:/Program Files/7-Zip"),
        Path("C:/7-Zip")
    ]
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "7z.exe").exists():
            return path
    
    # Buscar en PATH del sistema
    try:
        result = subprocess.run(["where", "7z.exe"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            return path
    except Exception:
        pass
    
    return None

def send_email(client: str, message: str) -> bool:
    """
    Envía un correo electrónico de notificación.
    
    Args:
        client: Nombre del cliente
        message: Contenido del mensaje
        
    Returns:
        True si el correo fue enviado correctamente, False en caso contrario
    """

    # Información de configuración del correo
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    try:
        # Verificar que tengamos credenciales
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            logger.warning("Credenciales de correo no configuradas. No se enviará notificación.")
            return False
            
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
            email_message["To"] = RECEIVER_EMAIL
            email_message["Subject"] = subject
            
            # Agregar cuerpo del mensaje
            email_message.attach(MIMEText(message, "plain"))
            
            # Enviar el correo
            server.send_message(email_message)
            
        logger.info(f"Correo enviado a {RECEIVER_EMAIL} - Asunto: {subject}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Error de autenticación al enviar correo: {e}")
        return False
    except Exception as e:
        logger.error(f"Error al enviar correo: {e}")
        return False

def manage_backup_limit(backup_dir: str, amount: int) -> bool:
    """
    Mantiene solo el número especificado de respaldos más recientes.
    
    Args:
        backup_dir: Directorio de respaldos
        amount: Cantidad máxima de respaldos a mantener
        
    Returns:
        True si la operación fue exitosa, False en caso contrario
    """
    try:
        if not amount or amount <= 0:
            logger.info("No se ha establecido límite de respaldos")
            return True
            
        backup_path = Path(backup_dir)
        files = list(backup_path.glob("*.7z"))
        
        # Ordenar por fecha de modificación (más reciente primero)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Eliminar archivos antiguos que exceden el límite
        if len(files) > amount:
            logger.info(f"Eliminando {len(files) - amount} respaldos antiguos")
            for file in files[amount:]:
                file.unlink()
                logger.info(f"Archivo antiguo eliminado: {file}")
                
        return True
    except Exception as e:
        logger.error(f"Error al gestionar límite de respaldos: {e}")
        return False

def save_state(filepath: str, state: Dict[str, Any]) -> bool:
    """
    Guarda el estado del programa en un archivo JSON de manera segura.
    
    Args:
        filepath: Ruta del archivo de estado
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
        logger.error(f"Error al guardar el estado: {e}")
        return False

def load_state(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Carga el estado del programa desde un archivo JSON con manejo de errores mejorado.
    
    Args:
        filepath: Ruta del archivo de estado
        
    Returns:
        Diccionario con el estado o None si hay error
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        logger.debug(f"Estado cargado desde {filepath}")
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
            logger.info(f"Se ha guardado una copia del archivo corrupto en {backup_path}")
        return None
    except Exception as e:
        logger.error(f"Error al cargar el estado: {e}")
        return None

def decrypt_backup_file(zip_path: str, password: str, output_dir: Optional[str] = None) -> Tuple[bool, str]:
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

# Inicializar estados
program_state = load_state(STATUS_PROGRAM) or {}
server_data_state = load_state(SERVER_DATA) or {}
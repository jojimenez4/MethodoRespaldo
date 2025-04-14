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
    self,
    password: str, 
    backup_dir: str, 
    client: str, 
    amount: int,
    server_data: Dict[str, Any],
    update_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Realiza un respaldo de la base de datos MySQL.
    
    Args:
        password: Contraseña encriptada del servidor MySQL
        backup_dir: Directorio donde se almacenará el backup
        client: Nombre del cliente
        amount: Cantidad máxima de backups a mantener
        server_data: Datos del servidor
        update_callback: Función de callback para actualizar el progreso
        
    Returns:
        True si el backup fue exitoso, False en caso contrario
    """
    try:
        import time
        import uuid
        import tempfile
        import subprocess
        
        # Validar parámetros de entrada
        backup_path = Path(backup_dir)
        if not backup_path.is_dir():
            try:
                backup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Directorio de respaldo creado: {backup_dir}")
            except Exception as e:
                raise ValueError(f"No se pudo crear el directorio {backup_dir}: {e}")
        
        if not client:
            raise ValueError("Se requiere un nombre de cliente válido")
        
        # Preparar nombres de archivos y rutas
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
        timestamp_email = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}"
        
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        
        # Sanitizar nombre del cliente para el archivo
        client = client.replace(" ", "_").replace("/", "_").replace("\\", "_")
        device = socket.gethostname()
        
        # Detectar rutas automáticamente
        mysql_bin_path = find_mysql_bin_path()
        seven_zip_path = find_7zip_path()
        
        # Verificar que las rutas existan
        if not mysql_bin_path:
            raise FileNotFoundError("No se pudo encontrar la instalación de MySQL")
        
        if not seven_zip_path:
            raise FileNotFoundError("No se pudo encontrar la instalación de 7-Zip")
        
        # Cambiar al directorio de MySQL y ejecutar el backup
        if update_callback:
            update_callback(10, "Iniciando respaldo...")
        
        # Crear directorio temporal único para este respaldo
        unique_id = str(uuid.uuid4())[:8]
        temp_dir = Path(tempfile.gettempdir()) / f"methodo_backup_{unique_id}"
        temp_dir.mkdir(exist_ok=True)
        
        # Usar un nombre único para el archivo temporal
        temp_backup_name = f"{client}_{device}_backup_{timestamp}_{unique_id}.sql"
        temp_backup_path = temp_dir / temp_backup_name
        
        logger.info(f"Iniciando respaldo SQL en {temp_backup_path}")
        
        
        mysqldump_cmd = [
            str(mysql_bin_path / "mysqldump"),
            "-e", "-R",
            "-u", USER,
            f"-p{decrypted_password}",
            DATABASE,
            f"--result-file={temp_backup_path}"
        ]
        
        # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
        safe_cmd = ' '.join(mysqldump_cmd).replace(decrypted_password, "********")
        logger.info(f"Ejecutando: {safe_cmd}")
        
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):
            # Crear información de startupinfo para ocultar ventanas en Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        process = subprocess.run(
            mysqldump_cmd, 
            shell=False, 
            capture_output=True, 
            text=True,
            check=False,  # No lanzar excepción para manejarla nosotros
            startupinfo=startupinfo,
            timeout=600  # 10 minutos máximo
        )
        
        if process.returncode != 0:
            logger.error(f"Error en mysqldump: {process.stderr}")
            raise subprocess.CalledProcessError(process.returncode, safe_cmd, 
                                              output=process.stdout, stderr=process.stderr)
        
        # Esperar a que el proceso libere el archivo
        time.sleep(1)
        
        # Verificar que el archivo se creó correctamente
        if not temp_backup_path.exists() or temp_backup_path.stat().st_size == 0:
            raise ValueError(f"No se pudo crear el archivo de respaldo: {temp_backup_path}")
        
        if update_callback:
            update_callback(50, "Comprimiendo respaldo...")

        # Verificar que el directorio destino tenga permisos de escritura
        try:
            test_file = backup_path / "test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            if test_file.exists():
                test_file.unlink()
            logger.info(f"Permisos de escritura verificados en: {backup_path}")
        except Exception as e:
            logger.error(f"Sin permisos de escritura en {backup_path}: {e}")
            raise ValueError(f"No se tienen permisos de escritura en el directorio de respaldo: {backup_path}")

        # Generar un nombre único para el archivo comprimido para evitar conflictos
        timestamp_with_millis = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]
        seven_zip_file_name = f"{client}_{device}_backup_{timestamp_with_millis}.7z"
        seven_zip_file_path = backup_path / seven_zip_file_name

        # Asegurarse de que no exista un archivo con el mismo nombre
        if seven_zip_file_path.exists():
            try:
                # Intentar eliminar el archivo existente
                seven_zip_file_path.unlink()
                logger.info(f"Archivo existente eliminado: {seven_zip_file_path}")
            except Exception as e:
                # Si no se puede eliminar, usar un nombre alternativo
                unique_id = str(uuid.uuid4())[:8]
                seven_zip_file_name = f"{client}_{device}_backup_{timestamp_with_millis}_{unique_id}.7z"
                seven_zip_file_path = backup_path / seven_zip_file_name
                logger.warning(f"No se pudo eliminar archivo existente, usando nombre alternativo: {seven_zip_file_path}")

        # Comprimir con 7-Zip
        logger.info(f"Comprimiendo respaldo en {seven_zip_file_path}")

        # Construir comando 7-Zip con opciones seguras
        compress_cmd = [
            str(seven_zip_path / "7z.exe"),
            "a",                           # Añadir a archivo
            "-y",                          # Asumir "sí" para todas las preguntas
            f"-p{BACKUP_PASSWORD}",        # Contraseña
            str(seven_zip_file_path),      # Archivo destino
            str(temp_backup_path)          # Archivo a comprimir
        ]

        # Ejecutar el comando de forma segura
        safe_compress_cmd = ' '.join(compress_cmd).replace(BACKUP_PASSWORD, "********")
        logger.info(f"Ejecutando: {safe_compress_cmd}")

        # Intentar comprimir con múltiples reintentos si es necesario
        max_compression_retries = 3
        for retry in range(max_compression_retries):
            try:
                seven_zip_process = subprocess.run(
                    compress_cmd, 
                    shell=False, 
                    capture_output=True, 
                    text=True,
                    check=False,
                    startupinfo=startupinfo,
                    timeout=300  # 5 minutos máximo
                )
                
                # Verificar resultado
                if seven_zip_process.returncode == 0:
                    logger.info("Compresión 7-Zip exitosa")
                    break
                else:
                    # Si falló, pero estamos en el último intento, lanzar excepción
                    if retry == max_compression_retries - 1:
                        logger.error(f"Error en 7-Zip después de {max_compression_retries} intentos: {seven_zip_process.stderr}")
                        raise subprocess.CalledProcessError(
                            seven_zip_process.returncode, 
                            safe_compress_cmd,
                            output=seven_zip_process.stdout, 
                            stderr=seven_zip_process.stderr
                        )
                    else:
                        # Si no es el último intento, esperar y reintentar
                        logger.warning(f"Error en 7-Zip (intento {retry+1}): {seven_zip_process.stderr}")
                        time.sleep((retry + 1) * 2)  # Esperar más tiempo en cada reintento
            except subprocess.TimeoutExpired:
                logger.error("Timeout durante la compresión")
                if retry == max_compression_retries - 1:
                    raise ValueError("La compresión no pudo completarse por timeout después de múltiples intentos")
                else:
                    time.sleep((retry + 1) * 2)
            except Exception as e:
                logger.error(f"Excepción durante la compresión: {e}")
                if retry == max_compression_retries - 1:
                    raise
                else:
                    time.sleep((retry + 1) * 2)

        # Verificar que el archivo comprimido se creó correctamente
        if not seven_zip_file_path.exists():
            raise ValueError(f"El archivo comprimido no fue creado: {seven_zip_file_path}")

        # Verificar tamaño del archivo comprimido
        file_size = seven_zip_file_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"El archivo comprimido está vacío: {seven_zip_file_path}")

        logger.info(f"Archivo comprimido creado: {seven_zip_file_path} ({file_size} bytes)")

        if update_callback:
            update_callback(70, "Eliminando archivo temporal...")

        # Eliminar archivo temporal con reintentos
        max_delete_retries = 5
        for retry in range(max_delete_retries):
            try:
                # Asegurar que los procesos han terminado
                if 'seven_zip_process' in locals() and seven_zip_process:
                    try:
                        if hasattr(seven_zip_process, 'kill'):
                            seven_zip_process.kill()
                    except:
                        pass
                        
                # Esperar un momento antes de intentar eliminar
                time.sleep(1)
                
                if temp_backup_path.exists():
                    temp_backup_path.unlink()
                    logger.info(f"Archivo temporal eliminado: {temp_backup_path}")
                    break
                else:
                    logger.info(f"Archivo temporal ya no existe: {temp_backup_path}")
                    break
            except Exception as e:
                if retry < max_delete_retries - 1:
                    logger.warning(f"Error al eliminar archivo temporal (intento {retry+1}): {e}")
                    time.sleep((retry + 1) * 2)  # Aumentar tiempo de espera con cada reintento
                else:
                    logger.error(f"No se pudo eliminar el archivo temporal después de {max_delete_retries} intentos")
                    # No fallar el respaldo por esto, continuar

        # Intentar eliminar el directorio temporal si está vacío
        try:
            temp_dir.rmdir()
        except:
            pass  # Ignorar errores al eliminar el directorio
        
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
    Busca la ruta de instalación de MySQL de manera más exhaustiva.
    
    Returns:
        Path a la carpeta bin de MySQL o None si no se encuentra
    """
    common_paths = [
        Path("C:/Program Files/MySQL/MySQL Server 8.0/bin"),
        Path("C:/Program Files/MySQL/MySQL Server 5.7/bin"),
        Path("C:/Program Files (x86)/MySQL/MySQL Server 8.0/bin"),
        Path("C:/Program Files (x86)/MySQL/MySQL Server 5.7/bin"),
        Path("C:/mysql/bin"),
        Path("C:/xampp/mysql/bin")
    ]
    
    # Buscar versiones adicionales de MySQL
    for i in range(0, 20):  # Buscar versiones desde 8.0 hasta 8.19
        version = f"8.{i}"
        common_paths.append(Path(f"C:/Program Files/MySQL/MySQL Server {version}/bin"))
        common_paths.append(Path(f"C:/Program Files (x86)/MySQL/MySQL Server {version}/bin"))
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "mysqldump.exe").exists():
            logger.info(f"MySQL encontrado en: {path}")
            return path
    
    # Buscar en PATH del sistema
    try:
        import shutil
        mysqldump_path = shutil.which("mysqldump")
        if mysqldump_path:
            path = Path(mysqldump_path).parent
            logger.info(f"MySQL encontrado en PATH: {path}")
            return path
        
        # Intentar con where en Windows
        result = subprocess.run(["where", "mysqldump"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            logger.info(f"MySQL encontrado con 'where': {path}")
            return path
    except Exception as e:
        logger.warning(f"Error al buscar MySQL en PATH: {e}")
    
    # Buscar en el registro de Windows
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for key_path in [
                r"SOFTWARE\MySQL AB",
                r"SOFTWARE\MySQL AB\MySQL Server 8.0",
                r"SOFTWARE\Wow6432Node\MySQL AB\MySQL Server 8.0"
            ]:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "Location")
                        if install_dir:
                            bin_path = Path(install_dir) / "bin"
                            if bin_path.exists() and (bin_path / "mysqldump.exe").exists():
                                logger.info(f"MySQL encontrado en registro: {bin_path}")
                                return bin_path
                except:
                    continue
    except:
        pass
    
    logger.warning("No se encontró la instalación de MySQL")
    return None

def find_7zip_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de 7-Zip de manera más exhaustiva.
    
    Returns:
        Path a la carpeta de 7-Zip o None si no se encuentra
    """
    common_paths = [
        Path("C:/Program Files/7-Zip"),
        Path("C:/Program Files (x86)/7-Zip"),
        Path("C:/7-Zip")
    ]
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "7z.exe").exists():
            logger.info(f"7-Zip encontrado en: {path}")
            return path
    
    # Buscar en PATH del sistema
    try:
        import shutil
        sevenzip_path = shutil.which("7z.exe")
        if sevenzip_path:
            path = Path(sevenzip_path).parent
            logger.info(f"7-Zip encontrado en PATH: {path}")
            return path
        
        # Intentar con where en Windows
        result = subprocess.run(["where", "7z.exe"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            logger.info(f"7-Zip encontrado con 'where': {path}")
            return path
    except Exception as e:
        logger.warning(f"Error al buscar 7-Zip en PATH: {e}")
    
    # Buscar en el registro de Windows
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for key_path in [
                r"SOFTWARE\7-Zip",
                r"SOFTWARE\Wow6432Node\7-Zip"
            ]:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "Path")
                        if install_dir:
                            path = Path(install_dir)
                            if path.exists() and (path / "7z.exe").exists():
                                logger.info(f"7-Zip encontrado en registro: {path}")
                                return path
                except:
                    continue
    except:
        pass
    
    logger.warning("No se encontró la instalación de 7-Zip")
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
    smtp_server = "webmail.methodo.cl"
    smtp_port = 25
    
    try:
        # Verificar que tengamos credenciales
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            logger.warning("Credenciales de correo no configuradas. No se enviará notificación.")
            return False
            
        # Usar with para asegurar que se cierre la conexión
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
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

def create_secure_temp_dir() -> Path:
    """
    Crea un directorio temporal seguro con permisos adecuados.
    
    Returns:
        Path al directorio temporal
    """
    import tempfile
    import os
    import uuid
    from pathlib import Path
    
    # Crear un nombre único para el directorio
    unique_id = str(uuid.uuid4())[:8]
    temp_base = Path(tempfile.gettempdir())
    
    # Crear un directorio específico para la aplicación
    app_temp_dir = temp_base / f"methodo_backup_{unique_id}"
    
    try:
        # Crear directorio con permisos explícitos si es posible
        app_temp_dir.mkdir(exist_ok=True)
        
        # En Windows, intentar establecer permisos si están disponibles los módulos
        if os.name == 'nt':
            try:
                # Intentar importar módulos sin causar error si no están disponibles
                win32security_imported = False
                try:
                    import win32security
                    import ntsecuritycon as con
                    import win32file
                    win32security_imported = True
                except ImportError:
                    logger.debug("Módulos win32security no disponibles, continuando sin establecer permisos explícitos")
                
                # Solo intentar establecer permisos si se importaron los módulos
                if win32security_imported:
                    # Obtener el SID del usuario actual
                    username = os.environ.get('USERNAME', 'SYSTEM')
                    domain = os.environ.get('USERDOMAIN', '')
                    
                    try:
                        # Intentar obtener SID del usuario actual o SYSTEM
                        sid, _, _ = win32security.LookupAccountName(domain, username)
                    except:
                        # Usar SYSTEM si falla
                        sid, _, _ = win32security.LookupAccountName('', 'SYSTEM')
                    
                    # Crear un nuevo descriptor de seguridad
                    security_descriptor = win32security.SECURITY_DESCRIPTOR()
                    acl = win32security.ACL()
                    
                    # Dar permisos completos al usuario actual o SYSTEM
                    acl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, sid)
                    
                    # Aplicar ACL al descriptor de seguridad
                    security_descriptor.SetSecurityDescriptorDacl(1, acl, 0)
                    
                    # Aplicar descriptor de seguridad al directorio
                    win32security.SetFileSecurity(
                        str(app_temp_dir), 
                        win32security.DACL_SECURITY_INFORMATION,
                        security_descriptor
                    )
                    
                    logger.debug(f"Permisos explícitos establecidos para el directorio temporal: {app_temp_dir}")
            except Exception as perm_error:
                logger.warning(f"No se pudieron establecer permisos explícitos: {perm_error}")
        
        return app_temp_dir
    except Exception as e:
        logger.error(f"Error al crear directorio temporal seguro: {e}")
        # Fallback al directorio temporal predeterminado
        return Path(tempfile.gettempdir())
    
def create_unique_temp_dir() -> Path:
    """
    Crea un directorio temporal único para evitar conflictos.
    
    Returns:
        Path al directorio temporal creado
    """
    import tempfile
    import uuid
    from pathlib import Path
    
    # Crear un nombre único para el directorio
    unique_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    base_temp = Path(tempfile.gettempdir())
    
    # Crear un directorio específico para este respaldo
    backup_temp_dir = base_temp / f"methodo_backup_{timestamp}_{unique_id}"
    
    try:
        backup_temp_dir.mkdir(exist_ok=True)        
        return backup_temp_dir
    except Exception as e:
        logger.error(f"Error al crear directorio temporal único: {e}")
        # En caso de error, usar el directorio temporal del sistema
        return Path(tempfile.gettempdir())
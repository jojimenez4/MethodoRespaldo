import os
import socket
import subprocess
import datetime
import base64
import mysql.connector
import pyodbc
import smtplib
import json
import logging
import time
import uuid
import tempfile
import shutil
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256
from contextlib import contextmanager
from typing import Tuple, Dict, Any, Optional, Union, Callable, Generator

# Asegurar que subprocess esté disponible para el linter
assert subprocess is not None

# Importar gestor de variables de entorno seguro
from env_manager import EnvManager, load_dotenv

# Configurar logging - Usar el mismo nombre que el resto de la aplicación
logger = logging.getLogger("BackupSystem")

# Cargar variables de entorno (usa env_manager en lugar de dotenv)
load_dotenv()

# Constantes de configuración (ahora usa EnvManager)
KEY = EnvManager.get("KEY", "").encode("utf-8")
USER = EnvManager.get("USER")
DATABASE = EnvManager.get("DATABASE")
EMAIL_ADDRESS = EnvManager.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = EnvManager.get("EMAIL_PASSWORD")
RECEIVER_EMAIL = EnvManager.get("RECEIVER_EMAIL")
BACKUP_PASSWORD = EnvManager.get("BACKUP_PASSWORD")
STATUS_PROGRAM = EnvManager.get("STATUS_PROGRAM", "status.json")
SERVER_DATA = EnvManager.get("SERVER_DATA", "server.json")

# Verificar variables críticas
if not KEY:
    logger.warning("KEY no configurada en variables de entorno. Se generará una clave temporal.")
    KEY = get_random_bytes(32)  # Generar clave temporal para esta sesión
    
if not BACKUP_PASSWORD:
    logger.warning("BACKUP_PASSWORD no configurada. Los respaldos podrían no ser seguros.")

# Log si está usando variables embebidas (compilado) o .env (desarrollo)
if EnvManager.is_embedded():
    logger.debug("Usando variables de entorno embebidas (modo compilado)")
else:
    logger.debug("Usando archivo .env (modo desarrollo)")

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
        
        # Generar nonce aleatorio (get_random_bytes siempre retorna bytes)
        nonce = get_random_bytes(16)
        
        # Crear cifrador AES en modo GCM (más seguro que CBC)
        cipher = AES.new(key_hash, AES.MODE_GCM, nonce=nonce)

        # Cifrar datos
        ciphertext, tag = cipher.encrypt_and_digest(source)
        
        # Combinar nonce + tag + texto cifrado (todo son bytes)
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
        # Validar formato de datos antes de procesar
        if not validate_encrypted_data(source):
            raise ValueError("Formato de datos encriptados inválido")
            
        # Decodificar si es necesario
        if decode:
            if isinstance(source, str):
                source = base64.b64decode(source)
            
        # Asegurar que source es bytes
        if isinstance(source, str):
            source = source.encode("utf-8")
            
        # Verificar que tenemos suficientes datos
        if len(source) < 32:
            raise ValueError("Datos encriptados insuficientes")
            
        # Generar hash de la clave para tener longitud fija
        key_hash = SHA256.new(key).digest()
        
        # Extraer nonce, tag y texto cifrado (todo como bytes)
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
def mysql_connection(host: str, port: int, password: str) -> Generator[Any, None, None]:
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
    except ValueError as ve:
        logger.error(f"Error de desencriptación en MySQL: {ve}")
        raise
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

@contextmanager
def sqlserver_connection(server: str, username: str, password: str, database: str = "") -> Generator[Any, None, None]:
    """
    Administra la conexión a SQL Server de forma segura usando context manager.
    
    Args:
        server: Nombre del servidor SQL Server
        username: Usuario de la base de datos
        password: Contraseña encriptada
        database: Nombre de la base de datos (opcional)
        
    Yields:
        Conexión activa a SQL Server
    """
    connection = None
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        
        # Construcción de la cadena de conexión
        if database:
            connection_string = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={decrypted_password}"
        else:
            connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        
        connection = pyodbc.connect(connection_string, timeout=60)
        connection.autocommit = True
        yield connection
    except ValueError as ve:
        logger.error(f"Error de desencriptación en SQL Server: {ve}")
        raise
    except pyodbc.Error as err:
        logger.error(f"Error de conexión SQL Server: {err}")
        raise
    finally:
        if connection:
            try:
                connection.close()
            except Exception as e:
                logger.error(f"Error al cerrar conexión SQL Server: {e}")

def bd_connect_sqlserver(server: str, username: str, password: str, database: str = "") -> Tuple[str, bool]:
    """
    Prueba la conexión a SQL Server y obtiene información del cliente.
    
    Args:
        server: Nombre del servidor SQL Server
        username: Usuario de la base de datos
        password: Contraseña encriptada
        database: Nombre de la base de datos (opcional)
        
    Returns:
        Tuple con (nombre_cliente, éxito_conexión)
    """
    try:
        with sqlserver_connection(server, username, password, database) as connection:
            cursor = connection.cursor()
            
            # Intentar obtener información del cliente desde varias tablas posibles
            client_queries = [
                "SELECT nombre FROM conf_sistema",
                "SELECT nombre_comision from centralizado.comision"
            ]
            
            client_name = None
            for query in client_queries:
                try:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    if result and result[0]:
                        client_name = result[0]
                        break
                except pyodbc.Error:
                    continue
            
            # Si no encontramos información del cliente, usar nombre del servidor
            if not client_name:
                client_name = f"Cliente_SQLServer_{server}"
            
            cursor.close()
            return client_name, True
            
    except pyodbc.Error as err:
        error_msg = f"Error en Base de Datos SQL Server: {err}"
        logger.error(error_msg)
        return error_msg, False
    except Exception as e:
        error_msg = f"Error inesperado en conexión SQL Server: {e}"
        logger.error(error_msg)
        return error_msg, False

def find_mysql_bin_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de MySQL de manera más exhaustiva.
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
    for i in range(0, 20):
        version = f"8.{i}"
        common_paths.append(Path(f"C:/Program Files/MySQL/MySQL Server {version}/bin"))
        common_paths.append(Path(f"C:/Program Files (x86)/MySQL/MySQL Server {version}/bin"))
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "mysqldump.exe").exists():
            return path
    
    # Buscar en PATH del sistema
    try:
        import shutil
        mysqldump_path = shutil.which("mysqldump")
        if mysqldump_path:
            path = Path(mysqldump_path).parent
            return path
        
        # Intentar con where en Windows
        result = subprocess.run(["where", "mysqldump"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            return path
    except Exception as e:
        logger.debug(f"Error al buscar MySQL en PATH: {e}")
    
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
                                return bin_path
                except:
                    continue
    except:
        pass
    
    logger.error("No se encontró la instalación de MySQL")
    return None

def find_7zip_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de 7-Zip de manera más exhaustiva.
    """
    common_paths = [
        Path("C:/Program Files/7-Zip"),
        Path("C:/Program Files (x86)/7-Zip"),
        Path("C:/7-Zip")
    ]
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists() and (path / "7z.exe").exists():
            return path
    
    # Buscar en PATH del sistema
    try:
        import shutil
        sevenzip_path = shutil.which("7z.exe")
        if sevenzip_path:
            path = Path(sevenzip_path).parent
            return path
        
        # Intentar con where en Windows
        result = subprocess.run(["where", "7z.exe"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip()).parent
            return path
    except Exception as e:
        logger.debug(f"Error al buscar 7-Zip en PATH: {e}")
    
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
                                return path
                except:
                    continue
    except:
        pass
    
    logger.error("No se encontró la instalación de 7-Zip")
    return None

def find_sqlcmd_path() -> Optional[Path]:
    """
    Busca la ruta de instalación de sqlcmd (SQL Server Command Line Utility).
    """
    common_paths = [
        Path("C:/Program Files/Microsoft SQL Server/Client SDK/ODBC/170/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/Client SDK/ODBC/130/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/Client SDK/ODBC/110/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/110/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/120/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/130/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/140/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files/Microsoft SQL Server/150/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/Client SDK/ODBC/170/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/Client SDK/ODBC/130/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/110/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/120/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/130/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/140/Tools/Binn/sqlcmd.exe"),
        Path("C:/Program Files (x86)/Microsoft SQL Server/150/Tools/Binn/sqlcmd.exe")
    ]
    
    # Buscar en rutas comunes
    for path in common_paths:
        if path.exists():
            return path
    
    # Buscar en PATH del sistema
    try:
        import shutil
        sqlcmd_path = shutil.which("sqlcmd")
        if sqlcmd_path:
            path = Path(sqlcmd_path)
            return path
        
        # Intentar con where en Windows
        result = subprocess.run(["where", "sqlcmd"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = Path(result.stdout.strip())
            return path
    except Exception as e:
        logger.debug(f"Error al buscar sqlcmd en PATH: {e}")
    
    # Buscar en el registro de Windows
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for key_path in [
                r"SOFTWARE\Microsoft\Microsoft SQL Server",
                r"SOFTWARE\Wow6432Node\Microsoft\Microsoft SQL Server"
            ]:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        # Buscar versiones instaladas
                        for i in range(10):  # Buscar hasta 10 versiones
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                if subkey_name.startswith("MSSQL"):
                                    continue
                                
                                # Intentar abrir la subkey
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    try:
                                        install_dir, _ = winreg.QueryValueEx(subkey, "InstallDir")
                                        if install_dir:
                                            bin_path = Path(install_dir) / "Tools" / "Binn" / "sqlcmd.exe"
                                            if bin_path.exists():
                                                return bin_path
                                    except:
                                        continue
                            except:
                                break
                except:
                    continue
    except:
        pass
    
    logger.error("No se encontró la instalación de sqlcmd")
    return None

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
        
        logger.info(f"Backup MySQL: {client} -> {backup_dir}")
        
        
        mysqldump_cmd = [
            str(mysql_bin_path / "mysqldump"),
            "-e", "-R",
            "-u", USER or "",
            f"-p{decrypted_password}",
            DATABASE or "",
            f"--result-file={str(temp_backup_path)}"
        ]
        
        # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
        safe_cmd = ' '.join(mysqldump_cmd).replace(decrypted_password or "", "********")
        logger.debug(f"Ejecutando: {safe_cmd}")
        
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
            check_file = backup_path / "check_write.tmp"
            with open(check_file, 'w') as f:
                f.write("check")
            if check_file.exists():
                check_file.unlink()
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
            except Exception:
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
        safe_compress_cmd = ' '.join(compress_cmd).replace(BACKUP_PASSWORD or "", "********")
        logger.debug(f"Ejecutando: {safe_compress_cmd}")

        # Intentar comprimir con múltiples reintentos si es necesario
        max_compression_retries = 3
        seven_zip_process = None  # Ensure variable is always defined
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
                        logger.debug(f"Error en 7-Zip (intento {retry+1}), reintentando...")
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

        if update_callback:
            update_callback(70, "Eliminando archivo temporal...")

        # Eliminar archivo temporal con reintentos
        max_delete_retries = 5
        for retry in range(max_delete_retries):
            try:
                # Esperar un momento antes de intentar eliminar
                time.sleep(1)
                
                if temp_backup_path.exists():
                    temp_backup_path.unlink()
                    break
                else:
                    break
            except Exception as e:
                if retry < max_delete_retries - 1:
                    logger.debug(f"Error al eliminar archivo temporal (intento {retry+1}): {e}")
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
        
        logger.info(f"Backup MySQL completado: {seven_zip_file_path.name} ({file_size} bytes)")
        return True
        
    except Exception as e:
        error_message = f"Error en el proceso de respaldo: {e}"
        logger.error(error_message, exc_info=True)
        send_email(client, f"Error ocurrido al respaldar datos: {e}")
        raise

def backup_sqlserver_database(
    server: str,
    username: str,
    password: str,
    database: str,
    backup_dir: str,
    client: str,
    amount: int,
    server_data: Dict[str, Any],
    update_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Realiza un respaldo de la base de datos SQL Server.
    
    Args:
        server: Nombre del servidor SQL Server
        username: Usuario de la base de datos
        password: Contraseña encriptada
        database: Nombre de la base de datos
        backup_dir: Directorio donde se almacenará el backup
        client: Nombre del cliente
        amount: Cantidad máxima de backups a mantener
        server_data: Datos del servidor
        update_callback: Función de callback para actualizar el progreso
        
    Returns:
        True si el backup fue exitoso, False en caso contrario
    """
    try:
        # Validar parámetros de entrada
        backup_path = Path(backup_dir)
        if not backup_path.is_dir():
            try:
                backup_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"No se pudo crear el directorio {backup_dir}: {e}")
        
        if not client:
            raise ValueError("Se requiere un nombre de cliente válido")
        
        if not database:
            raise ValueError("Se requiere un nombre de base de datos válido")
        
        # Preparar nombres de archivos y rutas
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
        timestamp_email = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}"
        
        # Log de inicio
        logger.info(f"Backup SQL Server: {client}/{database} ({server}) -> {backup_dir}")
        
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        
        # Sanitizar nombres para el archivo
        client = client.replace(" ", "_").replace("/", "_").replace("\\", "_")
        database = database.replace(" ", "_").replace("/", "_").replace("\\", "_")
        device = socket.gethostname()
        
        # Detectar ruta de sqlcmd
        sqlcmd_bin_path = find_sqlcmd_path()
        seven_zip_path = find_7zip_path()
        
        # Verificar que las rutas existan
        if not sqlcmd_bin_path:
            logger.error("No se pudo encontrar sqlcmd en el sistema")
            raise FileNotFoundError("No se pudo encontrar la instalación de sqlcmd. Verifique que SQL Server Command Line Utilities estén instalados.")
        
        if not seven_zip_path:
            logger.error("No se pudo encontrar 7-Zip en el sistema")
            raise FileNotFoundError("No se pudo encontrar la instalación de 7-Zip. Verifique que 7-Zip esté instalado.")
        
        # Cambiar al directorio de sqlcmd y ejecutar el backup
        if update_callback:
            update_callback(10, "Iniciando respaldo...")
        
        # Crear directorio temporal único para este respaldo
        # SQL Server necesita permisos de escritura, usar directorio público o específico
        unique_id = str(uuid.uuid4())[:8]
        
        # Intentar diferentes ubicaciones para el archivo temporal
        possible_temp_dirs = [
            Path("C:/temp"),  # Directorio público común
            Path("C:/Windows/temp"),  # Directorio de Windows
            Path(tempfile.gettempdir()),  # Directorio temporal del usuario
            backup_path  # Como último recurso, usar el directorio de destino
        ]
        
        temp_dir = None
        for temp_candidate in possible_temp_dirs:
            try:
                temp_test_dir = temp_candidate / f"methodo_sqlserver_backup_{unique_id}"
                temp_test_dir.mkdir(parents=True, exist_ok=True)
                
                # Probar escribir un archivo temporal
                check_file = temp_test_dir / "check_write.tmp"
                with open(check_file, 'w') as f:
                    f.write("check")
                check_file.unlink()
                
                temp_dir = temp_test_dir
                break
                
            except Exception:
                continue
        
        if not temp_dir:
            # Si ningún directorio temporal funciona, usar el directorio de destino directamente
            temp_dir = backup_path / f"temp_backup_{unique_id}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Usando directorio de destino para archivo temporal: {temp_dir}")
        
        # Usar un nombre único para el archivo temporal
        temp_backup_name = f"{client}_{device}_{database}_backup_{timestamp}_{unique_id}.bak"
        temp_backup_path = temp_dir / temp_backup_name
        
        # IMPORTANTE: En Windows, SQL Server necesita permisos específicos para escribir archivos
        # Verificar que el directorio tenga permisos adecuados
        try:
            # Dar permisos completos al directorio para todos los usuarios (temporalmente)
            import subprocess
            import os
            
            # Solo en Windows, intentar dar permisos al directorio
            if os.name == 'nt':
                try:
                    # Comando para dar permisos completos al directorio temporal
                    perm_cmd = f'icacls "{temp_dir}" /grant Users:F /t'
                    subprocess.run(perm_cmd, shell=True, capture_output=True, text=True, check=False)
                except Exception as perm_error:
                    logger.debug(f"No se pudieron configurar permisos: {perm_error}")
                    
        except Exception as e:
            logger.debug(f"Error al configurar permisos: {e}")
        
        # Preparar comando SQL para el respaldo
        backup_sql = f"BACKUP DATABASE [{database}] TO DISK = N'{temp_backup_path}' WITH FORMAT, INIT, NAME = N'{database}-Full Database Backup', SKIP, NOREWIND, NOUNLOAD, STATS = 10"
        
        # Comando sqlcmd - Usar autenticación de Windows si el server_type lo indica
        server_type = server_data.get("server_type", "")
        
        if "Windows Authentication" in server_type:
            # Autenticación de Windows - usar -E
            sqlcmd_cmd = [
                str(sqlcmd_bin_path),
                "-S", server,
                "-E",  # Usar autenticación de Windows
                "-Q", backup_sql
            ]
        else:
            # Autenticación SQL Server - usar -U y -P
            if not username:
                raise ValueError("Se requiere un nombre de usuario para autenticación SQL Server")
            if not decrypted_password:
                raise ValueError("Se requiere una contraseña para autenticación SQL Server")
            
            sqlcmd_cmd = [
                str(sqlcmd_bin_path),
                "-S", server,
                "-U", username,
                "-P", decrypted_password,
                "-Q", backup_sql
            ]
        
        # Ejecutar el comando de forma segura (sin mostrar contraseña en logs)
        if "Windows Authentication" in server_type:
            safe_cmd = ' '.join(sqlcmd_cmd)
        else:
            safe_cmd = ' '.join(sqlcmd_cmd).replace(decrypted_password, "********")
        logger.debug(f"Ejecutando: {safe_cmd}")
        
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):  # type: ignore
            startupinfo = subprocess.STARTUPINFO()  # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
            startupinfo.wShowWindow = subprocess.SW_HIDE  # type: ignore
        
        process = subprocess.run(  # type: ignore
            sqlcmd_cmd,
            shell=False,
            capture_output=True,
            text=True,
            check=False,
            startupinfo=startupinfo,
            timeout=1800  # 30 minutos máximo
        )
        
        # Log de salida del comando para diagnóstico
        
        if process.returncode != 0:
            error_details = f"Error en sqlcmd: Código de salida {process.returncode}"
            if process.stderr:
                error_details += f"\nSTDERR: {process.stderr.strip()}"
            if process.stdout:
                error_details += f"\nSTDOUT: {process.stdout.strip()}"
            logger.error(error_details)
            
            # Crear mensaje de error más específico para el usuario
            user_error_msg = "Error al ejecutar respaldo SQL Server:\n"
            if "login failed" in process.stderr.lower() or "login failed" in process.stdout.lower():
                user_error_msg += "- Falló la autenticación. Verifique credenciales o permisos de Windows."
            elif "network name cannot be found" in process.stderr.lower() or "network name cannot be found" in process.stdout.lower():
                user_error_msg += "- No se puede conectar al servidor. Verifique que el servidor SQL Server esté ejecutándose."
            elif "invalid object name" in process.stderr.lower() or "database" in process.stderr.lower():
                user_error_msg += "- La base de datos especificada no existe o no tiene permisos."
            else:
                user_error_msg += f"- Detalles técnicos: {process.stderr or process.stdout}"
            
            raise subprocess.CalledProcessError(process.returncode, safe_cmd,  # type: ignore
                                              output=process.stdout, stderr=user_error_msg)
        else:
            # Comando exitoso, pero verificar si hay mensajes de error en stdout
            stdout_content = process.stdout.strip().lower()
            if any(error_phrase in stdout_content for error_phrase in [
                'cannot open backup device', 'operating system error', 'acceso denegado',
                'access is denied', 'backup database is terminating abnormally'
            ]):
                logger.error("sqlcmd reportó éxito, pero hay errores en la salida:")
                logger.error(process.stdout)
                
                # Error específico de permisos
                if 'operating system error 5' in stdout_content or 'acceso denegado' in stdout_content:
                    error_msg = ("Error de permisos: SQL Server no puede escribir en el directorio especificado. "
                               "Esto puede ocurrir cuando SQL Server se ejecuta con una cuenta de servicio "
                               "que no tiene permisos en el directorio temporal.")
                    raise PermissionError(error_msg)
                else:
                    raise RuntimeError(f"SQL Server reportó errores durante el respaldo: {process.stdout}")
        
        logger.info("Comando sqlcmd ejecutado exitosamente")
        
        # Esperar a que el proceso libere el archivo
        time.sleep(1)
        
        # Verificar que el archivo se creó correctamente
        if not temp_backup_path.exists() or temp_backup_path.stat().st_size == 0:
            raise ValueError(f"No se pudo crear el archivo de respaldo: {temp_backup_path}")
        
        if update_callback:
            update_callback(50, "Comprimiendo respaldo...")
        
        # Verificar permisos de escritura en directorio destino
        try:
            check_file = backup_path / "check_write.tmp"
            with open(check_file, 'w') as f:
                f.write("check")
            if check_file.exists():
                check_file.unlink()
        except Exception as e:
            logger.error(f"Sin permisos de escritura en {backup_path}: {e}")
            raise ValueError(f"No se tienen permisos de escritura en el directorio de respaldo: {backup_path}")
        
        # Generar nombre único para archivo comprimido
        timestamp_with_millis = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]
        seven_zip_file_name = f"{client}_{device}_{database}_backup_{timestamp_with_millis}.7z"
        seven_zip_file_path = backup_path / seven_zip_file_name

        # Comprimir con 7-Zip
        compress_cmd = [
            str(seven_zip_path / "7z.exe"),
            "a",
            "-y",
            f"-p{BACKUP_PASSWORD}",
            str(seven_zip_file_path),
            str(temp_backup_path)
        ]
        
        safe_compress_cmd = ' '.join(compress_cmd).replace(BACKUP_PASSWORD or "", "********")
        logger.debug(f"Ejecutando: {safe_compress_cmd}")
        
        max_compression_retries = 3
        for retry in range(max_compression_retries):
            try:
                seven_zip_process = subprocess.run(  # type: ignore
                    compress_cmd,
                    shell=False,
                    capture_output=True,
                    text=True,
                    check=False,
                    startupinfo=startupinfo,
                    timeout=1200
                )
                
                if seven_zip_process.returncode == 0:
                    break
                else:
                    if retry == max_compression_retries - 1:
                        logger.error(f"Error en 7-Zip después de {max_compression_retries} intentos: {seven_zip_process.stderr}")
                        raise subprocess.CalledProcessError(  # type: ignore
                            seven_zip_process.returncode,
                            safe_compress_cmd,
                            output=seven_zip_process.stdout,
                            stderr=seven_zip_process.stderr
                        )
                    else:
                        logger.debug(f"Error en 7-Zip (intento {retry+1}), reintentando...")
                        time.sleep((retry + 1) * 2)
            except subprocess.TimeoutExpired:  # type: ignore
                logger.error("Timeout durante la compresión")
                if retry == max_compression_retries - 1:
                    raise ValueError("La compresión no pudo completarse por timeout")
                else:
                    time.sleep((retry + 1) * 2)
        
        # Verificar archivo comprimido
        if not seven_zip_file_path.exists():
            raise ValueError(f"El archivo comprimido no fue creado: {seven_zip_file_path}")
        
        file_size = seven_zip_file_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"El archivo comprimido está vacío: {seven_zip_file_path}")
        
        if update_callback:
            update_callback(70, "Eliminando archivo temporal...")
        
        # Eliminar archivo temporal con reintentos
        max_delete_retries = 5
        for retry in range(max_delete_retries):
            try:
                time.sleep(1)
                if temp_backup_path.exists():
                    temp_backup_path.unlink()
                    break
                else:
                    break
            except Exception as e:
                if retry < max_delete_retries - 1:
                    logger.debug(f"Error al eliminar archivo temporal (intento {retry+1}): {e}")
                    time.sleep((retry + 1) * 2)
                else:
                    logger.error(f"No se pudo eliminar el archivo temporal después de {max_delete_retries} intentos")
        
        # Intentar eliminar directorio temporal
        try:
            temp_dir.rmdir()
        except:
            pass
        
        if update_callback:
            update_callback(100, "Respaldo completado.")
        
        # Enviar correo de confirmación
        success_message = f"""
        Estimados, informamos que el respaldo de datos programado 
        para el dia de hoy, {timestamp_email}, se ha realizado y completado con exito.
        
        Base de datos: {database}
        Servidor: {server}

        Saluda atentamente,
        Mesa de ayuda Methodo.
        """
        send_email(client, success_message)
        
        # Gestionar límite de respaldos
        manage_backup_limit(backup_dir, amount)
        
        logger.info(f"Backup SQL Server completado: {seven_zip_file_path.name} ({file_size} bytes)")
        return True
        
    except Exception as e:
        error_message = f"Error en el proceso de respaldo SQL Server: {e}"
        logger.error(error_message, exc_info=True)
        send_email(client, f"Error ocurrido al respaldar datos SQL Server: {e}")
        return False

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
    smtp_server = "mail.methodo.cl"
    smtp_port = 25
    
    try:
        # Verificar que tengamos credenciales
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not RECEIVER_EMAIL:
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
            
        logger.debug(f"Correo enviado: {subject}")
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
            return True
            
        backup_path = Path(backup_dir)
        files = list(backup_path.glob("*.7z"))
        
        # Ordenar por fecha de modificación (más reciente primero)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Eliminar archivos antiguos que exceden el límite
        if len(files) > amount:
            logger.debug(f"Eliminando {len(files) - amount} respaldos antiguos")
            for file in files[amount:]:
                file.unlink()
                
        return True
    except Exception as e:
        logger.error(f"Error al gestionar límite de respaldos: {e}")
        return False

def save_state(filepath: Union[str, Path], state: Dict[str, Any], max_retries: int = 3) -> bool:
    """
    Guarda el estado del programa en un archivo JSON de manera segura con retry logic.
    
    Args:
        filepath: Ruta del archivo de estado
        state: Diccionario con el estado a guardar
        max_retries: Número máximo de reintentos
        
    Returns:
        True si la operación fue exitosa, False en caso contrario
    """
    filepath_obj = Path(filepath)
    
    for attempt in range(max_retries):
        try:
            # Asegurar que el directorio existe
            filepath_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Validar que el estado es JSON serializable
            try:
                json_str = json.dumps(state, ensure_ascii=False, indent=4)
            except (TypeError, ValueError) as e:
                logger.error(f"Estado no es JSON serializable: {e}")
                return False
            
            # Crear un archivo temporal con PID para evitar conflictos
            temp_filepath = filepath_obj.with_suffix(f".tmp{os.getpid()}")
            
            # Escribir en el archivo temporal
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())  # Forzar escritura al disco
            
            # Verificar que se escribió correctamente
            try:
                with open(temp_filepath, 'r', encoding='utf-8') as f:
                    verify_data = json.load(f)
                    if verify_data != state:
                        raise ValueError("Verificación falló: datos escritos no coinciden")
            except Exception as e:
                logger.error(f"Error al verificar archivo temporal: {e}")
                if temp_filepath.exists():
                    temp_filepath.unlink()
                continue
            
            # Crear backup del archivo actual si existe
            if filepath_obj.exists():
                backup_path = filepath_obj.with_suffix(f".bak")
                try:
                    shutil.copy2(filepath_obj, backup_path)
                except Exception as e:
                    logger.warning(f"No se pudo crear backup: {e}")
            
            # Reemplazar el archivo original
            if os.name == 'nt':
                # En Windows, necesitamos eliminar primero
                if filepath_obj.exists():
                    filepath_obj.unlink()
                temp_filepath.rename(filepath_obj)
            else:
                # En Unix, rename es atómico
                temp_filepath.rename(filepath_obj)
            
            logger.debug(f"Estado guardado exitosamente en {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error al guardar estado (intento {attempt + 1}/{max_retries}): {e}", exc_info=True)
            
            # Limpiar archivo temporal si existe
            temp_filepath = filepath_obj.with_suffix(f".tmp{os.getpid()}")
            if temp_filepath.exists():
                try:
                    temp_filepath.unlink()
                except:
                    pass
            
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                continue
            else:
                return False
    
    return False

def load_state(filepath: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """
    Carga el estado del programa desde un archivo JSON con manejo de errores mejorado.
    
    Args:
        filepath: Ruta del archivo de estado
        max_retries: Número máximo de reintentos
        
    Returns:
        Diccionario con el estado o None si hay error
    """
    filepath_obj = Path(filepath)
    
    for attempt in range(max_retries):
        try:
            if not filepath_obj.exists():
                logger.warning(f"Archivo de estado {filepath} no encontrado")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Validar que no está vacío
                if not content.strip():
                    logger.warning(f"Archivo {filepath} está vacío")
                    return None
                
                try:
                    state = json.loads(content)
                    
                    # Validar que es un diccionario
                    if not isinstance(state, dict):
                        logger.error(f"Archivo {filepath} no contiene un objeto JSON válido")
                        # Intentar recuperar desde backup
                        backup_path = filepath_obj.with_suffix(f".bak")
                        if backup_path.exists():
                            logger.info(f"Intentando recuperar desde backup")
                            try:
                                with open(backup_path, 'r', encoding='utf-8') as bf:
                                    backup_state = json.loads(bf.read())
                                    if isinstance(backup_state, dict):
                                        logger.info("Recuperación desde backup exitosa")
                                        shutil.copy2(backup_path, filepath)
                                        return backup_state
                            except Exception as be:
                                logger.error(f"Error al recuperar desde backup: {be}")
                        return None
                    
                    return state
                    
                except json.JSONDecodeError as e:
                    logger.error(f"El archivo de estado {filepath} está corrupto: {e}")
                    
                    # Intentar recuperar desde backup
                    backup_path = filepath_obj.with_suffix(f".bak")
                    if backup_path.exists():
                        logger.info(f"Intentando recuperar desde backup: {backup_path}")
                        try:
                            with open(backup_path, 'r', encoding='utf-8') as bf:
                                backup_state = json.loads(bf.read())
                                if isinstance(backup_state, dict):
                                    logger.info("Recuperación desde backup exitosa")
                                    shutil.copy2(backup_path, filepath)
                                    return backup_state
                        except Exception as be:
                            logger.error(f"Error al recuperar desde backup: {be}")
                    
                    # Hacer backup del archivo corrupto
                    corrupted_path = filepath_obj.with_suffix(f".corrupto.{int(time.time())}")
                    try:
                        shutil.copy2(filepath, corrupted_path)
                        logger.info(f"Copia del archivo corrupto guardada en {corrupted_path}")
                    except Exception as ce:
                        logger.error(f"No se pudo guardar copia del archivo corrupto: {ce}")
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Error al cargar estado (intento {attempt + 1}/{max_retries}): {e}", exc_info=True)
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                continue
            else:
                return None
    
    return None

def decrypt_backup_file(zip_path: Union[str, Path], password: str, output_dir: Optional[str] = None) -> Tuple[bool, str]:
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
            output_dir = str(zip_path.parent)
        else:
            output_path = Path(output_dir)
            if not output_path.exists():
                output_path.mkdir(parents=True)
        
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
        safe_cmd = ' '.join(extract_cmd).replace(password or "", "********")
        
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

def validate_encrypted_data(source: Union[str, bytes]) -> bool:
    """
    Valida que los datos encriptados tengan el formato correcto.
    
    Args:
        source: Datos encriptados a validar
        
    Returns:
        True si el formato es válido, False en caso contrario
    """
    try:
        # Si es string, debería ser base64 válido
        if isinstance(source, str):
            try:
                decoded = base64.b64decode(source)
            except Exception:
                logger.error("Los datos no son base64 válido")
                return False
        else:
            decoded = source
            
        # Verificar longitud mínima (nonce: 16 bytes + tag: 16 bytes + al menos 1 byte de datos)
        if len(decoded) < 33:
            logger.error(f"Datos insuficientes: {len(decoded)} bytes (mínimo 33)")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error al validar datos encriptados: {e}")
        return False

def diagnose_encryption_issues(encrypted_password: str) -> Dict[str, Any]:
    """
    Diagnostica problemas con datos encriptados.
    
    Args:
        encrypted_password: Contraseña encriptada problemática
        
    Returns:
        Diccionario con información de diagnóstico
    """
    diagnosis = {
        "is_base64_valid": False,
        "length_after_decode": 0,
        "has_minimum_length": False,
        "decryption_error": None,
        "suggestions": []
    }
    
    try:
        # Verificar si es base64 válido
        try:
            decoded = base64.b64decode(encrypted_password)
            diagnosis["is_base64_valid"] = True
            diagnosis["length_after_decode"] = len(decoded)
            diagnosis["has_minimum_length"] = len(decoded) >= 33
        except Exception:
            diagnosis["suggestions"].append("Los datos no son base64 válido")
            return diagnosis
            
        # Intentar desencriptar
        try:
            decrypt(KEY, encrypted_password)
            diagnosis["decryption_successful"] = True
        except Exception as e:
            diagnosis["decryption_error"] = str(e)
            diagnosis["decryption_successful"] = False
            
            # Sugerencias basadas en el error
            if "Incorrect padding" in str(e):
                diagnosis["suggestions"].append("Error de padding - posiblemente datos corruptos o clave incorrecta")
            elif "insuficientes" in str(e):
                diagnosis["suggestions"].append("Datos insuficientes - archivo de configuración corrupto")
            elif "Autenticación fallida" in str(e):
                diagnosis["suggestions"].append("Clave incorrecta o datos alterados")
            else:
                diagnosis["suggestions"].append(f"Error desconocido: {e}")
                
        # Verificar longitud
        if not diagnosis["has_minimum_length"]:
            diagnosis["suggestions"].append(f"Longitud insuficiente: {diagnosis['length_after_decode']} bytes (mínimo 33)")
            
        return diagnosis
        
    except Exception as e:
        diagnosis["suggestions"].append(f"Error general en diagnóstico: {e}")
        return diagnosis

def regenerate_encrypted_password(plain_password: str) -> str:
    """
    Regenera una contraseña encriptada usando las funciones actuales.
    
    Args:
        plain_password: Contraseña en texto plano
        
    Returns:
        Contraseña encriptada con el formato correcto
    """
    try:
        if not plain_password:
            raise ValueError("Se requiere una contraseña válida")
            
        # Encriptar la contraseña (siempre como string base64)
        encrypted = encrypt(KEY, plain_password, encode=True)
        
        # Verificar que se puede desencriptar
        decrypted = decrypt(KEY, encrypted).decode("utf-8")
        if decrypted != plain_password:
            raise ValueError("La encriptación/desencriptación no es consistente")
            
        logger.info("Contraseña regenerada exitosamente")
        return str(encrypted)
        
    except Exception as e:
        logger.error(f"Error al regenerar contraseña: {e}")
        raise

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
    import uuid
    
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
                win32security = None
                con = None
                win32file = None
                try:
                    import win32security
                    import ntsecuritycon as con
                    import win32file
                except ImportError:
                    pass
                
                # Solo intentar establecer permisos si se importaron todos los módulos
                if win32security is not None and con is not None and win32file is not None:
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


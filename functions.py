import os
import dotenv
import socket
import subprocess
import datetime
import base64
import mysql.connector
import pyodbc
import smtplib
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Hash import SHA256

dotenv.load_dotenv()

KEY = os.getenv("KEY").encode("utf-8")
USER = os.getenv("USER")
DATABASE = os.getenv("DATABASE")
EMAIL_ADRESS = os.getenv("EMAIL_ADRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

def encrypt(key, source, encode=True):
    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size) 
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data

def decrypt(key, source, decode=True):
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

def bd_connect_mysql(host, port, password):
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connect = [host, port, USER, decrypted_password, DATABASE]
        connection = mysql.connector.connect(
            host=connect[0],
            port=connect[1],
            user=connect[2],
            password=connect[3],
            database=connect[4]
        )
        cursor = connection.cursor()
        cursor.execute("SELECT nombre FROM conf_sistema")
        result = cursor.fetchone()
        connection.close()
        if result:
            return result[0], True
        else:
            return "Nombre no encontrado en conf_sistema", False
    except mysql.connector.Error as err:
        return f"Error en Base de Datos: {err}", False
    except Exception as e:
        return f"Un error inesperado a ocurrido: {e}", False

# def bd_server_verify_sql_server(server, username, password):
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        connection = pyodbc.connect(connection_string)
        connection.close()
        return True
    except pyodbc.Error as err:
        print(f"Error during SQL Server server verification: {err}")
        return False
    
def backup_mysql_database(password, backup_dir, client, update_callback=None):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
    timestamp_email = timestamp[:4] + "-" + timestamp[4:6] + "-" + timestamp[6:8] + " " + timestamp[8:10] + ":" + timestamp[10:12]
    decrypted_password = decrypt(KEY, password).decode("utf-8")
    if " " in client:
        client = client.replace(" ", "_")
    device = socket.gethostname()
    backup_file_name = f"{client}_{device}_backup_{timestamp}.txt"
    rar_file_name = f"{client}_{device}_backup_{timestamp}.rar"
    
    mysql_bin_path = "C:\\mysql\\bin"
    rar_path = "C:\\WinRAR"

    command = f'mysqldump -e -R -u root -p{decrypted_password} {DATABASE} > "{backup_file_name}"'
    move_command = f'move {backup_file_name} {rar_path}'
    comprimir_command = f'"rar" a -p {rar_file_name} {backup_file_name}"'
    delete_txt = f'del {backup_file_name}'
    move_command2 = f'move {rar_file_name} {backup_dir}'

    try:
        os.chdir(mysql_bin_path)
        if update_callback:
            update_callback(10, "Iniciando respaldo...")
        subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        if update_callback:
            update_callback(30, "Moviendo archivo temporal...")
        subprocess.run(move_command, shell=True, check=True)

        os.chdir(rar_path)
        if update_callback:
            update_callback(50, "Comprimiendo respaldo...")     
        rar_process = subprocess.run(comprimir_command, shell=True, input=BACKUP_PASSWORD, capture_output=True, text=True)
        if rar_process.returncode != 0:
            print(f"RAR Output: {rar_process.stdout}")
            print(f"RAR Error: {rar_process.stderr}")
            raise subprocess.CalledProcessError(rar_process.returncode, comprimir_command)

        if update_callback:
            update_callback(70, "Eliminando archivo temporal...")
        subprocess.run(delete_txt, shell=True, check=True)
        if update_callback:
            update_callback(90, "Moviendo respaldo a destino...")
        subprocess.run(move_command2, shell=True, check=True)
        if update_callback:
            update_callback(100, "Respaldo completado.")
        message = f"""
                Estimados,
                Informamos que el respaldo de datos programado para el dia de hoy, {timestamp_email}, 
                se ha realizado y completado con exito.

                Saluda atentamente,
                Mesa de ayuda Methodo.
                """
        send_email(client, message)
    except subprocess.CalledProcessError as e:
        send_email(client, f"Error ocurrido al respaldar datos: {e}")
    except OSError as e:
        send_email(client, f"Error ocurrido al respaldar datos: {e}")
    except Exception as e:
        send_email(client, f"Error inesperado: {e}")
    
# # def backup_sql_server_database(server, user, password, dbname, backup_dir):
#     timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
#     backup_file = os.path.join(backup_dir, f"{dbname}_backup_{timestamp}.bak")
#     command = f"sqlcmd -S {server} -U {user} -P {password} -Q \"BACKUP DATABASE [{dbname}] TO DISK='{backup_file}'\""
#     try:
#         subprocess.run(command, shell=True, check=True)
#         print(f"Backup of SQL Server database '{dbname}' completed successfully.")
#     except subprocess.CalledProcessError as e:
#         print(f"Error occurred while backing up SQL Server database: {e}")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")

def send_email(client, message):
    receiver_email = "jose.jimenez@methodo.cl"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_ADRESS, EMAIL_PASSWORD)
            subject = f"Respaldo completado con exito. Cliente: {client}"
            if "Error" in message:
                subject = f"Respaldo interrumpido por error. Cliente: {client}"
            email_message = f"Subject: {subject}\n\n{message}"
            server.sendmail(EMAIL_ADRESS, receiver_email, email_message)
            server.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(f"Error occurred while sending email: {e}")
    except Exception as e:
        print(f"Error occurred while sending email: {e}")
    return True


import os
import subprocess
import datetime
import base64
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Hash import SHA256
import mysql.connector
import pyodbc

KEY = b"METHODO_PROVIDENCIA2025"  # encryption key
user = "root"

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
    decryptor = AES.new(key, AES.MODE_CBC, IV)  # Correctly initialize the AES decryptor with the mode
    data = decryptor.decrypt(source[AES.block_size:])
    padding = data[-1]
    if data[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid padding...")
    return data[:-padding]

def bd_server_verify_mysql(IP, port, username, password):
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection = mysql.connector.connect(
            host=IP,
            port=port,
            user=username,
            password=decrypted_password
        )
        connection.close()
        return True
    except mysql.connector.Error as err:
        print(f"Error during MySQL server verification: {err}")
        return False

def bd_server_verify_sql_server(server, username, password):
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        connection = pyodbc.connect(connection_string)
        connection.close()
        return True
    except pyodbc.Error as err:
        print(f"Error during SQL Server server verification: {err}")
        return False

def backup_mysql_database(password, backup_dir):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
    backup_file_name = f"prueba_backup_{timestamp}.txt"
    rar_file_name = f"prueba_backup_{timestamp}.rar"
    decrypted_password = decrypt(KEY, password).decode("utf-8")
    
    mysql_bin_path = "C:\\mysql\\bin"
    mysqldump_path = os.path.join(mysql_bin_path, "mysqldump")
    rar_path = "C:\\WinRAR"

    command = f'"{mysqldump_path}" -e -R -u root -p"{decrypted_password}" bdpos > "{backup_file_name}"'
    move_command = f'move {backup_file_name} {rar_path}'
    comprimir_command = f'"rar" a -p- {rar_file_name} {backup_file_name}"'
    delete_txt = f'del {backup_file_name}'
    move_command2 = f'move {rar_file_name} {backup_dir}'

    try:
        os.chdir(mysql_bin_path)
        subprocess.run(command, shell=True, check=True)
        subprocess.run(move_command, shell=True, check=True)
        os.chdir(rar_path)
        
        rar_process = subprocess.run(comprimir_command, shell=True, input=password, capture_output=True, text=True)
        if rar_process.returncode != 0:
            print(f"RAR Output: {rar_process.stdout}")
            print(f"RAR Error: {rar_process.stderr}")
            raise subprocess.CalledProcessError(rar_process.returncode, comprimir_command)

        subprocess.run(delete_txt, shell=True, check=True)
        subprocess.run(move_command2, shell=True, check=True)
        print(f"Backup of MySQL database completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up MySQL database: {e}")
    except OSError as e:
        print(f"Error changing directory: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def backup_sql_server_database(server, user, password, dbname, backup_dir):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    backup_file = os.path.join(backup_dir, f"{dbname}_backup_{timestamp}.bak")
    
    command = f"sqlcmd -S {server} -U {user} -P {password} -Q \"BACKUP DATABASE [{dbname}] TO DISK='{backup_file}'\""
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Backup of SQL Server database '{dbname}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up SQL Server database: {e}")

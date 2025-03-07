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

def bd_login_verify_mysql(IP, port, username, password):
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
        print(f"Error during MySQL login verification: {err}")
        return False

def bd_login_verify_sql_server(server, username, password):
    try:
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        connection = pyodbc.connect(connection_string)
        connection.close()
        return True
    except pyodbc.Error as err:
        print(f"Error during SQL Server login verification: {err}")
        return False

def backup_mysql_database(password, db_name, backup_dir):
    timestamp = datetime.datetime.now().strftime('%YYYY%mm%d%H%M')
    backup_file = os.path.join(backup_dir, f"{db_name}_backup_{timestamp}.txt")
    
    command = f"mysqldump -e -R -u root -p {password} {db_name} > {backup_file}"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Backup of MySQL database '{db_name}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up MySQL database: {e}")

def backup_sql_server_database(server, user, password, db_name, backup_dir):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    backup_file = os.path.join(backup_dir, f"{db_name}_backup_{timestamp}.bak")
    
    command = f"sqlcmd -S {server} -U {user} -P {password} -Q \"BACKUP DATABASE [{db_name}] TO DISK='{backup_file}'\""
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Backup of SQL Server database '{db_name}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up SQL Server database: {e}")

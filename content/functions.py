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
    decrypted_password = decrypt(KEY, password).decode("utf-8")
    
    mysql_bin_path = "C:\\mysql\\bin"
    mysqldump_path = os.path.join(mysql_bin_path, "mysqldump")
    
    command = f'"{mysqldump_path}" -e -R -u root -p"{decrypted_password}" bdpos > "{backup_file_name}"'
    
    # Construct the move command
    move_command = f'move "{backup_file_name}" "{backup_dir}"'
    
    try:
        # Change the current directory to the MySQL bin directory
        os.chdir(mysql_bin_path)
        
        # Execute the mysqldump command
        subprocess.run(command, shell=True, check=True)
        
        # Move the backup file to the backup directory
        subprocess.run(move_command, shell=True, check=True, cwd=mysql_bin_path)
        
        print(f"Backup of MySQL database completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up MySQL database: {e}")
    except OSError as e:
        print(f"Error changing directory: {e}")

def backup_sql_server_database(server, user, password, dbname, backup_dir):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    backup_file = os.path.join(backup_dir, f"{dbname}_backup_{timestamp}.bak")
    
    command = f"sqlcmd -S {server} -U {user} -P {password} -Q \"BACKUP DATABASE [{dbname}] TO DISK='{backup_file}'\""
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Backup of SQL Server database '{dbname}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up SQL Server database: {e}")

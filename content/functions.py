import os
import subprocess
import datetime
import base64
import mysql.connector
import pyodbc
import smtplib
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Hash import SHA256

KEY = os.getenv("KEY_DECRYPT").encode("utf-8")
user = os.getenv("USER")
sender_email = os.getenv("EMAIL_ADRESS")
sender_password = os.getenv("EMAIL_PASSWORD")

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



#MYSQL CONNEXION

def backup_mysql_database(password, backup_dir, rar_password):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
    backup_file_name = f"prueba_backup_{timestamp}.txt"
    rar_file_name = f"prueba_backup_{timestamp}.rar"
    decrypted_password = decrypt(KEY, password).decode("utf-8")  # Desencriptar la contraseña de la base de datos
    
    mysql_bin_path = "C:\\mysql\\bin"
    rar_path = "C:\\WinRAR"

<<<<<<< HEAD
    # Comando para realizar el respaldo de la base de datos
    command = f'"{mysqldump_path}" -e -R -u root -p"{decrypted_password}" bdpos > "{backup_file_name}"'
    move_command = f'move {backup_file_name} {rar_path}'
    comprimir_command = f'"rar" a -p{rar_password} {rar_file_name} {backup_file_name}'
=======
    command = f'mysqldump -e -R -u root -p{decrypted_password} bdpos > "{backup_file_name}"'
    move_command = f'move {backup_file_name} {rar_path}'
    comprimir_command = f'"rar" a -p {rar_file_name} {backup_file_name}"'
>>>>>>> origin/dev
    delete_txt = f'del {backup_file_name}'
    move_command2 = f'move {rar_file_name} {backup_dir}'

    try:
        # Cambiar al directorio de MySQL bin
        os.chdir(mysql_bin_path)
<<<<<<< HEAD
        subprocess.run(command, shell=True, check=True)
        
        # Mover el archivo de respaldo al directorio de WinRAR
=======
        subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
>>>>>>> origin/dev
        subprocess.run(move_command, shell=True, check=True)
        
        # Cambiar al directorio de WinRAR
        os.chdir(rar_path)
        
<<<<<<< HEAD
        # Ejecutar el comando de compresión con la contraseña en texto plano
        rar_process = subprocess.run(comprimir_command, shell=True, capture_output=True, text=True)
=======
        rar_process = subprocess.run(comprimir_command, shell=True, input=decrypted_password, capture_output=True, text=True)
>>>>>>> origin/dev
        if rar_process.returncode != 0:
            print(f"RAR Output: {rar_process.stdout}")
            print(f"RAR Error: {rar_process.stderr}")
            raise subprocess.CalledProcessError(rar_process.returncode, comprimir_command)

        # Eliminar el archivo de texto original
        subprocess.run(delete_txt, shell=True, check=True)
        
        # Mover el archivo comprimido al directorio de destino
        subprocess.run(move_command2, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up MySQL database: {e}")
    except OSError as e:
        print(f"Error changing directory: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")






    #MYSQL SERVER CONEXION
    
def backup_sql_server_database(server, user, password, dbname, backup_dir):
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    backup_file = os.path.join(backup_dir, f"{dbname}_backup_{timestamp}.bak")
    
    command = f"sqlcmd -S {server} -U {user} -P {password} -Q \"BACKUP DATABASE [{dbname}] TO DISK='{backup_file}'\""
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Backup of SQL Server database '{dbname}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while backing up SQL Server database: {e}")
<<<<<<< HEAD
        
        
        
    


        
        
        
        
        
=======
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def send_email(message):
    receiver_email = "jose.jimenez@methodo.cl"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            email_message = f"Subject: Aviso Respaldo\n\n{message}"
            server.sendmail(sender_email, receiver_email, email_message)
            server.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(f"Error occurred while authenticating: {e}")
    except Exception as e:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            email_message = f"Subject: Aviso Respaldo\n\n{message}"
            server.sendmail(sender_email, receiver_email, email_message)
            server.quit()
    return True
>>>>>>> origin/dev

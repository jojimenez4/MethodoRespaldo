import os
import subprocess
import datetime

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

# Example usage:
# backup_mysql_database('localhost', 'root', 'password', 'my_database', '/path/to/backup/dir')
# backup_sql_server_database('localhost', 'sa', 'password', 'my_database', '/path/to/backup/dir')
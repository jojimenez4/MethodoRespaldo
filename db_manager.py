"""
Módulo para gestionar conexiones y operaciones de base de datos.
Separa la lógica de base de datos del resto de la aplicación.
"""

import mysql.connector
import pyodbc
import logging
from contextlib import contextmanager
from typing import Tuple, Dict, Any, Optional, List, Generator
from functions import decrypt, KEY, USER, logger

@contextmanager
def mysql_connection(host: str, port: int, password: str, user: str, database: str) -> Generator[Any, None, None]:
    """
    Administra la conexión a MySQL de forma segura usando context manager.
    
    Args:
        host: Host del servidor MySQL
        port: Puerto del servidor MySQL
        password: Contraseña encriptada
        user: Usuario de la base de datos
        database: Nombre de la base de datos
        
    Yields:
        Conexión activa a MySQL
    """
    connection = None
    try:
        # Incluir parámetros adicionales para mejorar la estabilidad
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=USER,
            password=decrypted_password,
            database=database,
            connection_timeout=60,  # Mayor timeout para conexiones lentas
            autocommit=True,        # Evitar problemas de transacciones
            use_pure=True,          # Usar implementación pura de Python para mayor compatibilidad
            auth_plugin='mysql_native_password'  # Especificar plugin de autenticación
        )
        yield connection
    except mysql.connector.Error as err:
        logger.error(f"Error de conexión MySQL: {err}")
        raise
    finally:
        # Asegurar cierre seguro de la conexión
        if connection:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception as e:
                logger.error(f"Error al cerrar conexión MySQL: {e}")

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
    except pyodbc.Error as err:
        logger.error(f"Error de conexión SQL Server: {err}")
        raise
    finally:
        if connection:
            try:
                connection.close()
            except Exception as e:
                logger.error(f"Error al cerrar conexión SQL Server: {e}")

class DatabaseManager:
    """Clase para gestionar operaciones de base de datos."""
    
    def __init__(self, server_data: Dict[str, Any]):
        """
        Inicializa el administrador de base de datos.
        
        Args:
            server_data: Datos de conexión al servidor
        """
        self.server_data = server_data
        self.user = server_data.get("user", "sa")
        self.database = server_data.get("database", "")
    
    def check_connection(self) -> Tuple[str, bool]:
        """
        Verifica la conexión a la base de datos.
        
        Returns:
            Tuple con (mensaje, estado_conexión)
        """
        server_type = self.server_data.get("server_type")
        
        if server_type == "MySQL Server (TCP/IP)":
            return self._check_mysql_connection()
        elif server_type == "SQL Server (Windows Authentication)":
            return self._check_sqlserver_connection()
        else:
            return "Tipo de servidor no soportado", False
    
    def _check_mysql_connection(self) -> Tuple[str, bool]:
        """
        Verifica la conexión a MySQL y obtiene información del cliente.
        
        Returns:
            Tuple con (nombre_cliente, éxito_conexión)
        """
        try:
            host = self.server_data.get("host", "localhost")
            port = self.server_data.get("port", 3306)
            password = self.server_data.get("password", "")
            
            with mysql_connection(host, port, password, self.user, self.database) as connection:
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
    
    def _check_sqlserver_connection(self) -> Tuple[str, bool]:
        """
        Verifica la conexión a SQL Server y obtiene información del cliente.
        
        Returns:
            Tuple con (nombre_cliente, éxito_conexión)
        """
        try:
            server = self.server_data.get("host", "localhost")
            username = self.server_data.get("user", "sa")
            password = self.server_data.get("password", "")
            database = self.server_data.get("database", "")
            
            with sqlserver_connection(server, username, password, database) as connection:
                cursor = connection.cursor()
                
                # Intentar obtener información del cliente desde varias tablas posibles
                client_queries = [
                    "SELECT TOP 1 nombre_cliente FROM conf_sistema",
                    "SELECT TOP 1 nombre_cliente FROM configuracion", 
                    "SELECT TOP 1 cliente FROM conf_sistema",
                    "SELECT TOP 1 cliente FROM configuracion",
                    "SELECT TOP 1 name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')"
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

    def get_database_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre la base de datos conectada.
        
        Returns:
            Diccionario con información de la BD
        """
        info = {
            "type": self.server_data.get("server_type", "Desconocido"),
            "host": self.server_data.get("host", "localhost"),
            "port": self.server_data.get("port", "N/A"),
            "database": self.database,
            "tables": [],
            "size": "Desconocido",
            "version": "Desconocida"
        }
        
        try:
            if info["type"] == "MySQL Server (TCP/IP)":
                self._get_mysql_info(info)
            elif info["type"] == "SQL Server (Windows Authentication)":
                self._get_sqlserver_info(info)
        except Exception as e:
            logger.error(f"Error al obtener información de la base de datos: {e}")
        
        return info
    
    def _get_mysql_info(self, info: Dict[str, Any]) -> None:
        """
        Obtiene información detallada de MySQL.
        
        Args:
            info: Diccionario a completar con la información
        """
        host = self.server_data.get("host", "localhost")
        port = self.server_data.get("port", 3306)
        password = self.server_data.get("password", "")
        
        with mysql_connection(host, port, password, self.user, self.database) as connection:
            with connection.cursor() as cursor:
                # Obtener versión
                cursor.execute("SELECT VERSION()")
                result = cursor.fetchone()
                info["version"] = result[0] if result else "Desconocida"
                
                # Obtener tablas
                cursor.execute("SHOW TABLES")
                info["tables"] = [table[0] for table in cursor.fetchall()]
                
                # Obtener tamaño de la base de datos
                cursor.execute(f"""
                    SELECT 
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb 
                    FROM 
                        information_schema.tables 
                    WHERE 
                        table_schema = '{self.database}'
                """)
                result = cursor.fetchone()
                info["size"] = f"{result[0]} MB" if result and result[0] else "0 MB"
    
    def _get_sqlserver_info(self, info: Dict[str, Any]) -> None:
        """
        Obtiene información detallada de SQL Server.
        
        Args:
            info: Diccionario a completar con la información
        """
        server = self.server_data.get("host", "localhost")
        username = self.server_data.get("user", "sa")
        password = self.server_data.get("password", "")
        database = self.server_data.get("database", "")
        
        with sqlserver_connection(server, username, password, database) as connection:
            cursor = connection.cursor()
            
            # Obtener versión
            cursor.execute("SELECT @@VERSION")
            result = cursor.fetchone()
            info["version"] = result[0].split('\n')[0] if result else "Desconocida"
            
            # Obtener tablas
            if database:
                cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = '{database}'")
            else:
                cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
            info["tables"] = [table[0] for table in cursor.fetchall()]
            
            # Obtener tamaño de la base de datos
            if database:
                cursor.execute(f"""
                    SELECT 
                        CONVERT(DECIMAL(10,2), SUM(size) * 8.0 / 1024) AS size_mb
                    FROM 
                        sys.master_files
                    WHERE 
                        DB_NAME(database_id) = '{database}'
                """)
                result = cursor.fetchone()
                info["size"] = f"{result[0]} MB" if result and result[0] else "0 MB"
            else:
                info["size"] = "N/A"
            
            cursor.close()

    def get_databases(self) -> List[str]:
        """
        Obtiene la lista de bases de datos disponibles.
        
        Returns:
            Lista de nombres de bases de datos
        """
        databases = []
        
        try:
            server_type = self.server_data.get("server_type")
            
            if server_type == "MySQL Server (TCP/IP)":
                host = self.server_data.get("host", "localhost")
                port = self.server_data.get("port", 3306)
                password = self.server_data.get("password", "")
                
                with mysql_connection(host, port, password, self.user, "") as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SHOW DATABASES")
                        databases = [db[0] for db in cursor.fetchall() 
                                   if db[0] not in ('information_schema', 'performance_schema', 'mysql', 'sys')]
            
            elif server_type == "SQL Server (Windows Authentication)":
                server = self.server_data.get("host", "localhost")
                username = self.server_data.get("user", "sa")
                password = self.server_data.get("password", "")
                
                with sqlserver_connection(server, username, password, "") as connection:
                    cursor = connection.cursor()
                    cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')")
                    databases = [db[0] for db in cursor.fetchall()]
                    cursor.close()
            
        except Exception as e:
            logger.error(f"Error al obtener lista de bases de datos: {e}")
        
        return databases
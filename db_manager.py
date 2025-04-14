"""
Módulo para gestionar conexiones y operaciones de base de datos.
Separa la lógica de base de datos del resto de la aplicación.
"""

import mysql.connector
import pyodbc
import logging
from contextlib import contextmanager
from typing import Tuple, Dict, Any, Optional, List, Generator
from functions import decrypt, KEY, logger

@contextmanager
def mysql_connection(host: str, port: int, password: str, user: str, database: str) -> Generator[mysql.connector.connection.MySQLConnection, None, None]:
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
            user=user,
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
                    logger.debug("Conexión MySQL cerrada correctamente")
            except Exception as e:
                logger.error(f"Error al cerrar conexión MySQL: {e}")

class DatabaseManager:
    """Clase para gestionar operaciones de base de datos."""
    
    def __init__(self, server_data: Dict[str, Any]):
        """
        Inicializa el administrador de base de datos.
        
        Args:
            server_data: Datos de conexión al servidor
        """
        self.server_data = server_data
        self.user = server_data.get("user", "root")
        self.database = server_data.get("database", "")
    
    def test_connection(self) -> Tuple[str, bool]:
        """
        Prueba la conexión a la base de datos.
        
        Returns:
            Tuple con (mensaje, estado_conexión)
        """
        server_type = self.server_data.get("server_type")
        
        if server_type == "MySQL Server (TCP/IP)":
            return self._test_mysql_connection()
        elif server_type == "SQL Server (Windows Authentication)":
            return self._test_sqlserver_connection()
        else:
            return "Tipo de servidor no soportado", False
    
    def _test_mysql_connection(self) -> Tuple[str, bool]:
        """
        Prueba la conexión a MySQL y obtiene información del cliente.
        
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
    
    def _test_sqlserver_connection(self) -> Tuple[str, bool]:
        """
        Prueba la conexión a SQL Server.
        
        Returns:
            Tuple con (mensaje, éxito_conexión)
        """
        try:
            server = self.server_data.get("host", "localhost")
            username = self.server_data.get("user", "sa")
            password = self.server_data.get("password", "")
            
            decrypted_password = decrypt(KEY, password).decode("utf-8")
            connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
            
            with pyodbc.connect(connection_string) as connection:
                # Intentar obtener información del cliente
                cursor = connection.cursor()
                try:
                    cursor.execute("SELECT TOP 1 nombre_cliente FROM conf_sistema")
                    result = cursor.fetchone()
                    client_name = result[0] if result else "Cliente SQL Server"
                except:
                    client_name = "Cliente SQL Server"
                finally:
                    cursor.close()
                
                return client_name, True
        except pyodbc.Error as err:
            logger.error(f"Error durante la verificación del servidor SQL Server: {err}")
            return str(err), False
        except Exception as e:
            logger.error(f"Error inesperado en verificación SQL Server: {e}")
            return str(e), False
    
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
                info["version"] = cursor.fetchone()[0]
                
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
        
        decrypted_password = decrypt(KEY, password).decode("utf-8")
        connection_string = f"DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={decrypted_password}"
        
        with pyodbc.connect(connection_string) as connection:
            cursor = connection.cursor()
            
            # Obtener versión
            cursor.execute("SELECT @@VERSION")
            info["version"] = cursor.fetchone()[0].split('\n')[0]
            
            # Obtener tablas
            cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
            info["tables"] = [table[0] for table in cursor.fetchall()]
            
            # Obtener tamaño de la base de datos
            cursor.execute(f"""
                SELECT 
                    CONVERT(DECIMAL(10,2), SUM(size) * 8 / 1024) AS size_mb
                FROM 
                    sys.master_files
                WHERE 
                    DB_NAME(database_id) = '{self.database}'
            """)
            result = cursor.fetchone()
            info["size"] = f"{result[0]} MB" if result and result[0] else "0 MB"
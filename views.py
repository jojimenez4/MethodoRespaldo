from __future__ import annotations
import os    
import datetime
import subprocess
import time
import threading
import schedule
import customtkinter
import pystray
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from config_manager import ConfigManager
from auth_manager import AuthManager
from users_management import UserManagementWindow
import logging

from functions import (
    encrypt, bd_connect_mysql, bd_connect_sqlserver, send_email,
    save_state, program_state, server_data_state, KEY, STATUS_PROGRAM, 
    SERVER_DATA, decrypt_backup_file, logger
)
from backup_manager import BackupManager

# Configurar apariencia inicial
customtkinter.set_appearance_mode("dark") 

# Diccionario para almacenar ventanas activas
active_windows = {}

# Variables de estado
class AppState:
    running: bool = True
    task_configurations: List[Tuple[str, str]] = []
    backup_hours: Optional[int] = None
    backup_minutes: Optional[int] = None
    scheduled: bool = False
    scheduled_backup_thread: Optional[threading.Thread] = None
    selected_amount: int = 0
    app_icon: Optional[Any] = None
    root_window: Optional[customtkinter.CTk] = None
    backup_in_progress: bool = False  # Flag para prevenir ejecuciones múltiples
    _lock = threading.Lock()  # Para operaciones thread-safe
    
    @classmethod
    def set_amount(cls, amount: int) -> None:
        with cls._lock:
            cls.selected_amount = amount
    
    @classmethod
    def set_scheduled(cls, value: bool) -> None:
        with cls._lock:
            cls.scheduled = value
    
    @classmethod
    def set_backup_time(cls, hours: int, minutes: int) -> None:
        with cls._lock:
            cls.backup_hours = hours
            cls.backup_minutes = minutes

# Funciones de utilidad
def center_window(window, width: int, height: int) -> None:
    """Centrar una ventana en la pantalla."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def load_app_image(filename: str) -> Image.Image:
    """Carga una imagen desde el directorio de assets."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_dir, "assets", filename)
    
    # Verificar si la imagen existe
    if not os.path.exists(image_path):
        logger.warning(f"Imagen no encontrada: {image_path}")
        # Crear una imagen en blanco si no se encuentra
        return Image.new('RGB', (200, 200), color='gray')
    
    return Image.open(image_path)

# Interfaz de login
def create_login_interface():
    """Crea la interfaz de inicio de sesión."""
    # Inicializar ConfigManager para crear archivos de configuración
    try:
        config = ConfigManager()
        logger.info("Archivos de configuración inicializados")
    except Exception as e:
        logger.warning(f"Error inicializando configuración: {e}")
    
    login_window = customtkinter.CTk()
    login_window.title("Login - Sistema de Respaldo")
    center_window(login_window, 400, 600)

    # Variable para el modo oscuro/claro
    switch = customtkinter.StringVar(value="dark")

    def switch_mode():
        """Cambia entre modo oscuro y claro."""
        if switch.get() == "dark":
            customtkinter.set_appearance_mode("light")
            button.configure(text="Modo claro")
            switch.set("light")
        else:
            customtkinter.set_appearance_mode("dark")
            button.configure(text="Modo oscuro")
            switch.set("dark")

    # Marco principal
    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Botón de cambio de tema
    button = customtkinter.CTkSwitch(frame, command=switch_mode, text="Modo oscuro")
    button.pack(pady=10, padx=10, anchor="ne")

    # Logo
    logo_image = load_app_image("METHODO.png")
    logo_ctk_image = customtkinter.CTkImage(light_image=logo_image, dark_image=logo_image, size=(200, 200))
    logo_label = customtkinter.CTkLabel(frame, image=logo_ctk_image, text="")
    logo_label.pack(pady=10)
    
    # Campos de entrada
    username_label = customtkinter.CTkLabel(frame, text="Usuario:", width=20)
    username_label.pack(pady=5)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.pack(pady=5)

    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    # Mensaje de error (oculto inicialmente)
    error_label = customtkinter.CTkLabel(frame, text="", text_color="red")
    error_label.pack(pady=5)
    error_label.configure(text="")  # Ocultar inicialmente

    # Contador de intentos
    login_attempts = {"count": 0}
    
    # Inicializar AuthManager
    auth_manager = AuthManager()

    # Verificación de credenciales
    def verify_login():
        """Verifica las credenciales de inicio de sesión."""
        username = username_entry.get()
        password = password_entry.get()
        
        # Validación básica
        if not username or not password:
            error_label.configure(text="Por favor, complete todos los campos")
            return
        
        # Verificar con AuthManager
        success, user_data = auth_manager.verify_credentials(username, password)
        
        if success:
            # El log ya se genera en auth_manager.verify_credentials()
            login_window.destroy()
            
            # Verificar si tenemos una sesión en curso
            if program_state.get("running") == True:
                server_type = server_data_state.get("server_type")
                if server_type == "MySQL Server (TCP/IP)":
                    host = server_data_state.get("host")
                    port = server_data_state.get("port")
                    password = server_data_state.get("password")
                    
                    # Verificar que los datos necesarios estén disponibles
                    if not host or not port or not password:
                        logger.error("Datos de conexión incompletos en el estado del servidor")
                        messagebox.showerror("Error", "Datos de conexión incompletos.")
                        create_server_interface()
                        return
                    
                    # Verificar conexión
                    connection_result = bd_connect_mysql(host, port, password)
                    connection_success = connection_result[1]
                    
                    if connection_success:
                        open_backup_interface(server_data_state)
                    else:
                        logger.error(f"Error de conexión a BD: {connection_result[0]}")
                        messagebox.showerror("Error", "No se pudo conectar a la base de datos.")
                        create_server_interface()
                elif server_type == "SQL Server (Windows Authentication)":
                    host = server_data_state.get("host")
                    user = server_data_state.get("user")
                    database = server_data_state.get("database")
                    password = server_data_state.get("password")
                    
                    # Verificar que los datos necesarios estén disponibles
                    if not host or not user or not database or not password:
                        logger.error("Datos de conexión incompletos en el estado del servidor SQL Server")
                        messagebox.showerror("Error", "Datos de conexión incompletos.")
                        create_server_interface()
                        return
                    
                    # Verificar conexión
                    connection_result = bd_connect_sqlserver(host, user, password, database)
                    connection_success = connection_result[1]
                    
                    if connection_success:
                        open_backup_interface(server_data_state)
                    else:
                        logger.error(f"Error de conexión a SQL Server: {connection_result[0]}")
                        messagebox.showerror("Error", "No se pudo conectar a la base de datos SQL Server.")
                        create_server_interface()
                else:
                    create_server_interface()
            else:
                create_server_interface()
        else:
            # Incrementar contador de intentos fallidos
            login_attempts["count"] += 1
            
            # Mostrar mensaje de error
            error_label.configure(text=f"Usuario o contraseña incorrectos. Intento {login_attempts['count']}/3")
            
            # Limpiar campo de contraseña
            password_entry.delete(0, "end")
            
            # Bloquear temporalmente después de 3 intentos
            if login_attempts["count"] >= 3:
                error_label.configure(text="Demasiados intentos fallidos. Espere 30 segundos.")
                username_entry.configure(state="disabled")
                password_entry.configure(state="disabled")
                login_button.configure(state="disabled")
                
                # Desbloquear después de 30 segundos
                def unlock_login():
                    login_attempts["count"] = 0
                    error_label.configure(text="")
                    username_entry.configure(state="normal")
                    password_entry.configure(state="normal")
                    login_button.configure(state="normal")
                
                login_window.after(30000, unlock_login)

    # Botón de inicio de sesión
    login_button = customtkinter.CTkButton(frame, text="Iniciar sesión", command=verify_login, fg_color="green")
    login_button.pack(pady=20)

    # Vincular tecla Enter para iniciar sesión
    password_entry.bind("<Return>", lambda event: verify_login())

    # Manejo del cierre de la ventana
    def on_closing():
        AppState.running = False
        login_window.destroy()

    login_window.protocol("WM_DELETE_WINDOW", on_closing)
    login_window.mainloop()

# Interfaz de selección de servidor
def create_server_interface() -> None:
    """Crea la interfaz para conectar al servidor de base de datos."""
    server_window = customtkinter.CTk() 
    server_window.title("Conectar al Servidor de Base de Datos")
    center_window(server_window, 800, 500)

    frame = customtkinter.CTkFrame(server_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Selección de tipo de servidor
    server_type_label = customtkinter.CTkLabel(frame, text="Tipo de Servidor:", width=30)
    server_type_label.pack(pady=5)
    server_type = customtkinter.CTkComboBox(
        frame, 
        values=["Seleccionar Base de Datos", "MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"], 
        width=280
    )
    server_type.set("Seleccionar Base de Datos")
    server_type.pack(pady=5)

    # Frame para IP y puerto
    ip_port_frame = customtkinter.CTkFrame(frame, fg_color=frame.cget("fg_color"))
    ip_port_frame.pack(pady=5, padx=5, fill="x")

    # Campos de entrada para IP y puerto
    server_ip_label = customtkinter.CTkLabel(ip_port_frame, text="Dirección IP del Servidor:", width=30)
    server_ip_label.pack(side="left", pady=5, padx=(110, 0))
    server_ip_entry = customtkinter.CTkEntry(ip_port_frame)
    server_ip_entry.insert(0, "localhost")
    server_ip_entry.pack(side="left", pady=5, padx=(0, 10))

    port_label = customtkinter.CTkLabel(ip_port_frame, text="Puerto:", width=10)
    port_label.pack(side="left", pady=5, padx=(10, 0))
    port_entry = customtkinter.CTkEntry(ip_port_frame)
    port_entry.insert(0, "3306")
    port_entry.pack(side="left", pady=5, padx=(0, 10))

    # Frame para usuario (solo para SQL Server)
    user_frame = customtkinter.CTkFrame(frame, fg_color=frame.cget("fg_color"))
    user_frame.pack(pady=5, padx=5, fill="x")

    user_label = customtkinter.CTkLabel(user_frame, text="Usuario:", width=30)
    user_label.pack(side="left", pady=5, padx=(110, 0))
    user_entry = customtkinter.CTkEntry(user_frame)
    user_entry.insert(0, "sa")
    user_entry.pack(side="left", pady=5, padx=(0, 10))

    # Frame para base de datos (solo para SQL Server)
    database_frame = customtkinter.CTkFrame(frame, fg_color=frame.cget("fg_color"))
    database_frame.pack(pady=5, padx=5, fill="x")

    database_label = customtkinter.CTkLabel(database_frame, text="Base de Datos(s):", width=30)
    database_label.pack(side="left", pady=5, padx=(110, 0))
    database_entry = customtkinter.CTkEntry(database_frame, width=250)
    database_entry.pack(side="left", pady=5, padx=(0, 10))
    
    # Label de ayuda para múltiples bases
    db_help_label = customtkinter.CTkLabel(
        database_frame, 
        text="Separe con ; para múltiples bases", 
        font=("Arial", 9),
        text_color="gray"
    )
    db_help_label.pack(side="left", pady=5, padx=(5, 0))

    # Campo de contraseña
    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    # Inicialmente ocultar campos específicos de SQL Server
    user_frame.pack_forget()
    database_frame.pack_forget()

    # Función para mostrar/ocultar campos según tipo de servidor
    def on_server_type_change(selected_type):
        if selected_type == "SQL Server (Windows Authentication)":
            user_frame.pack(pady=5, padx=5, fill="x", before=password_label)
            database_frame.pack(pady=5, padx=5, fill="x", before=password_label)
            port_entry.delete(0, "end")
            port_entry.insert(0, "1433")
        else:
            user_frame.pack_forget()
            database_frame.pack_forget()
            port_entry.delete(0, "end")
            port_entry.insert(0, "3306")

    # Vincular cambio de tipo de servidor
    server_type.configure(command=on_server_type_change)

    # Verificación de conexión al servidor
    def verify_server() -> None:
        """Verifica la conexión al servidor seleccionado."""
        try:
            host = server_ip_entry.get().strip()
            
            # Validaciones básicas
            if not host:
                raise ValueError("La dirección del servidor no puede estar vacía")
                
            try:
                port = int(port_entry.get().strip())
                if port <= 0 or port > 65535:
                    raise ValueError("El puerto debe estar entre 1 y 65535")
            except ValueError:
                raise ValueError("El puerto debe ser un número entero válido")
                
            password = password_entry.get()
            if not password:
                raise ValueError("La contraseña no puede estar vacía")
                
            # Encriptar contraseña
            encrypted_password = encrypt(KEY, password.encode("utf-8"))
            server_type_selected = server_type.get()
            
            # Procesar según tipo de servidor
            if server_type_selected == "MySQL Server (TCP/IP)":
                # Convertir encrypted_password de bytes a str para la función de conexión
                password_str: str = encrypted_password.decode('latin-1') if isinstance(encrypted_password, bytes) else str(encrypted_password)
                client, connection_success = bd_connect_mysql(host, port, password_str)
                
                if connection_success:
                    # Guardar configuración de conexión
                    server_data = {
                        "server_type": server_type_selected,
                        "host": host,
                        "port": port,
                        "password": encrypted_password,
                        "client": client,
                        "last_connection": datetime.datetime.now().isoformat()
                    }
                    
                    save_state(SERVER_DATA, server_data)
                    messagebox.showinfo("Éxito", f"Conexión exitosa a la base de datos MySQL. Cliente: {client}")
                    
                    logger.info(f"Conexión exitosa a MySQL: {host}:{port} - Cliente: {client}")
                    server_window.destroy()
                    open_backup_interface(server_data)
                else:
                    logger.error(f"Error en conexión MySQL: {client}")
                    messagebox.showerror("Error", f"Error en la conexión a la base de datos MySQL: {client}")
            
            elif server_type_selected == "SQL Server (Windows Authentication)":
                username = user_entry.get().strip()
                databases_input = database_entry.get().strip()
                
                if not username:
                    raise ValueError("El nombre de usuario no puede estar vacío")
                
                if not databases_input:
                    raise ValueError("El nombre de la base de datos no puede estar vacío")
                
                # Separar bases de datos por punto y coma
                databases = [db.strip() for db in databases_input.split(';') if db.strip()]
                
                if not databases:
                    raise ValueError("Debe especificar al menos una base de datos")
                
                # Verificar conexión con la primera base de datos
                first_database = databases[0]
                # Convertir encrypted_password de bytes a str para la función de conexión
                password_str: str = encrypted_password.decode('latin-1') if isinstance(encrypted_password, bytes) else str(encrypted_password)
                client, connection_success = bd_connect_sqlserver(host, username, password_str, first_database)
                
                if connection_success:
                    # Inicializar ConfigManager
                    config_manager = ConfigManager()
                    
                    # IMPORTANTE: Limpiar servidores existentes para evitar duplicados
                    config_manager.clear_all_servers()
                    logger.info("Servidores anteriores limpiados, configurando nuevos servidores")
                    
                    # Crear entrada para cada base de datos en servers.json
                    success_count = 0
                    for idx, database in enumerate(databases, start=1):
                        server_config = {
                            "id": f"server_{idx}",
                            "name": f"{client} - {database}",
                            "enabled": True,
                            "server_type": server_type_selected,
                            "host": host,
                            "port": port,
                            "user": username,
                            "database": database,
                            "password": encrypted_password,
                            "client": client
                        }
                        
                        # Agregar o actualizar servidor
                        if config_manager.add_server(server_config):
                            success_count += 1
                            # El log ya se genera en config_manager.add_server()
                    
                    # Guardar configuración de conexión para compatibilidad
                    server_data = {
                        "server_type": server_type_selected,
                        "host": host,
                        "port": port,
                        "user": username,
                        "database": first_database,  # Primera base para interfaz principal
                        "password": encrypted_password,
                        "client": client,
                        "last_connection": datetime.datetime.now().isoformat()
                    }
                    
                    save_state(SERVER_DATA, server_data)
                    
                    # Construir mensaje de éxito
                    if len(databases) == 1:
                        # Mensaje para una sola base de datos (mensaje tradicional)
                        message = f"Conexión exitosa a la base de datos SQL Server.\n\nCliente: {client}"
                    else:
                        # Mensaje para múltiples bases de datos
                        db_list = ", ".join(databases)
                        message = (
                            f"Conexión exitosa a la base de datos SQL Server.\n\n"
                            f"Cliente: {client}\n"
                            f"Configuradas {len(databases)} bases de datos:\n{db_list}"
                        )
                    
                    messagebox.showinfo("Éxito", message)
                    
                    logger.info(f"Conexión exitosa a SQL Server: {host}:{port} - {len(databases)} base(s) de datos")
                    server_window.destroy()
                    open_backup_interface(server_data)
                else:
                    logger.error(f"Error en conexión SQL Server: {client}")
                    messagebox.showerror("Error", f"Error en la conexión a la base de datos SQL Server: {client}")
            else:
                messagebox.showerror("Error", "No se ha seleccionado ninguna base de datos.")
        except ValueError as ve:
            messagebox.showerror("Error de validación", str(ve))
        except Exception as e:
            logger.error(f"Error al conectar a la base de datos: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Botón de conexión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    # Vincular tecla Enter para conectar
    password_entry.bind("<Return>", lambda event: verify_server())
    
    server_window.mainloop()
    
# Interfaz de desencriptación de archivos
def open_file_interface(parent_window: customtkinter.CTk) -> None:
    """Crea la interfaz para desencriptar archivos de respaldo."""
    if "decrypt_window" in active_windows and active_windows["decrypt_window"].winfo_exists():
        active_windows["decrypt_window"].lift()
        active_windows['decrypt_window'].focus_force()
        return
    file_window = customtkinter.CTk()
    active_windows["decrypt_window"] = file_window
    file_window.title("Desencriptar Archivo de Respaldo")
    center_window(file_window, 500, 400)

    frame = customtkinter.CTkFrame(file_window)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Título
    label = customtkinter.CTkLabel(
        frame, 
        text="Desencriptar Archivo de Respaldo", 
        font=("Helvetica", 18, "bold"), 
        width=40
    )
    label.pack(pady=15, padx=5)

    # Etiqueta para mostrar el archivo seleccionado
    file_label = customtkinter.CTkLabel(
        frame, 
        text="Ningún archivo seleccionado", 
        font=("Arial", 12), 
        width=40,
        corner_radius=10, 
        fg_color="gray"
    )
    file_label.pack(pady=10, fill="x", expand=True)

    # Variables para almacenar rutas
    file_path = ""
    output_dir = ""

    # Selección de archivo
    def select_file() -> None:
        nonlocal file_path
        selected_path = filedialog.askopenfilename(filetypes=[("7-Zip Files", "*.7z"), ("All Files", "*.*")])
        parent = file_window
        if selected_path:
            file_path = selected_path
            file_label.configure(text=f"Archivo: {Path(selected_path).name}")
            file_window.after(100, lambda: file_window.focus_force())
        else:
            file_path = ""
            file_label.configure(text="Ningún archivo seleccionado")
    
    browse_button = customtkinter.CTkButton(
        frame, 
        text="📂 Buscar Archivo", 
        command=select_file, 
        fg_color="green"
    )
    browse_button.pack(pady=10)

    # Seleccionar carpeta destino
    def select_output_dir() -> None:
        nonlocal output_dir
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            output_dir = selected_dir
            output_dir_label.configure(text=f"Destino: {Path(selected_dir).name}")
        else:
            output_dir = ""
            output_dir_label.configure(text="Destino predeterminado")

    output_dir_label = customtkinter.CTkLabel(
        frame,
        text="Destino predeterminado",
        font=("Arial", 12),
        width=40,
        corner_radius=10,
        fg_color="gray"
    )
    output_dir_label.pack(pady=10, fill="x", expand=True)

    output_dir_button = customtkinter.CTkButton(
        frame,
        text="📁 Seleccionar Destino",
        command=select_output_dir,
        fg_color="blue"
    )
    output_dir_button.pack(pady=5)

    # Desencriptar archivo
    def decrypt_file() -> None:
        nonlocal file_path, output_dir
        
        if not file_path:
            messagebox.showerror("Error", "No se ha seleccionado ningún archivo.")
            return

        # Solicitar contraseña
        password = simpledialog.askstring(
            "Contraseña", 
            "Ingrese la contraseña del archivo:", 
            show="*"
        )
        
        if not password:
            messagebox.showerror("Error", "No se ingresó ninguna contraseña.")
            return
            
        # Mostrar ventana de progreso
        progress_window = customtkinter.CTkToplevel(file_window)
        progress_window.title("Desencriptando")
        center_window(progress_window, 300, 100)
        progress_frame = customtkinter.CTkFrame(progress_window)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=10)
        progress_label = customtkinter.CTkLabel(progress_frame, text="Desencriptando archivo...")
        progress_label.pack(pady=10)
        progress_window.update()
        
        # Desencriptar en un hilo separado
        def run_decrypt():
            try:
                success, message = decrypt_backup_file(
                    file_path, 
                    password, 
                    output_dir if output_dir else None
                )
                
                # Actualizar UI en el hilo principal
                file_window.after(0, lambda: complete_decrypt(success, message))
            except Exception as e:
                file_window.after(0, lambda: complete_decrypt(False, str(e)))
                
        def complete_decrypt(success, message):
            progress_window.destroy()
            if success:
                messagebox.showinfo("Éxito", message)
            else:
                messagebox.showerror("Error", message)
        
        # Iniciar proceso de desencriptación
        threading.Thread(target=run_decrypt, daemon=True).start()

    decrypt_button = customtkinter.CTkButton(
        frame, 
        text="🔓 Desencriptar", 
        command=decrypt_file, 
        fg_color="blue"
    )
    decrypt_button.pack(pady=20)

    # Manejo del cierre de la ventana
    def on_closing() -> None:
        parent_window.deiconify()
        active_windows.pop("decrypt_window", None)
        file_window.destroy()

    file_window.protocol("WM_DELETE_WINDOW", on_closing)
    file_window.mainloop()

# Interfaz principal de respaldo
def open_backup_interface(server_data: Dict[str, Any]) -> None:
    """Crea la interfaz principal para la gestión de respaldos."""
    global program_state

    # Cargar estado de programación anterior y configurar
    config_manager = ConfigManager()
    program_state = config_manager.get_program_state()
    
    # Cargar tareas programadas del nuevo sistema
    backup_tasks = config_manager.get_backup_tasks()
    if backup_tasks:
        AppState.set_scheduled(True)
        AppState.selected_amount = program_state.get("amount", 5)
        
        # Para compatibilidad con la UI, obtener la primera tarea de frecuencia
        freq_tasks = [t for t in backup_tasks if t.get("type") == "frequency" and t.get("enabled", True)]
        if freq_tasks:
            AppState.set_backup_time(freq_tasks[0].get("hours", 4), freq_tasks[0].get("minutes", 0))
        
        logger.info(f"Cargadas {len(backup_tasks)} tarea(s) de respaldo")
    
    root = customtkinter.CTk()
    AppState.root_window = root
    root.title("Sistema de Respaldo - Methodo")
    center_window(root, 600, 400)

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=5, padx=5, fill="both", expand=True)

    # Cargar logo
    logo_image = load_app_image("METHODO.png")
    logo_ctk_image = customtkinter.CTkImage(light_image=logo_image, dark_image=logo_image, size=(200, 200))

    # Panel superior con logo y botones
    top_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
    top_frame.pack(pady=10, padx=10, fill="x")

    logo_label = customtkinter.CTkLabel(top_frame, image=logo_ctk_image, text="")
    logo_label.pack(side="left", padx=50)

    # Marco para botones
    buttons_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
    buttons_frame.pack(side="right", padx=10)

    # Información de cliente
    client_name = server_data.get("client", "Cliente no identificado")
    client_label = customtkinter.CTkLabel(
        buttons_frame, 
        text=f"Cliente: {client_name}", 
        font=("Arial", 14, "bold")
    )
    client_label.pack(pady=5, anchor="e")

    # Botones de acciones
    history_button = customtkinter.CTkButton(
        buttons_frame, 
        text="⟳ Historial", 
        width=30, 
        command=lambda: show_backup_history(rounded_label), 
        fg_color="green"
    )
    history_button.pack(pady=5, anchor="e")

    eye_button = customtkinter.CTkButton(
        buttons_frame, 
        text="👁 Desencriptar", 
        width=30, 
        command=lambda: open_file_interface(root), 
        fg_color="RoyalBlue1"
    )
    eye_button.pack(pady=5, anchor="e")

    # Botón de configuración avanzada (se define más abajo)
    advanced_settings_button = None

    # Marco para selección de carpeta
    def update_label() -> Optional[str]:
        """Actualiza la etiqueta con la carpeta seleccionada y guarda en status.json."""
        nonlocal folder_path
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=folder)
            folder_path = folder  # Actualizar variable local
            
            # Guardar inmediatamente en status.json
            try:
                from config_manager import ConfigManager
                config_manager = ConfigManager()
                config_manager.update_program_state(backup_dir=folder)
                logger.info(f"Directorio de backup guardado: {folder}")
            except Exception as e:
                logger.error(f"Error guardando directorio de backup: {e}")
                # Fallback: guardar directamente en program_state
                program_state["backup_dir"] = folder
                save_state(STATUS_PROGRAM, program_state)
            
            return folder
        else:
            messagebox.showerror("Error", "No se seleccionó ninguna carpeta.")
            return None

    # Cargar ícono de lupa
    lupa_image = load_app_image("lupa.png")
    lupa_ctk_image = customtkinter.CTkImage(light_image=lupa_image, dark_image=lupa_image, size=(30, 30))

    lupa_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
    lupa_frame.pack(pady=10, padx=10, fill="x")

    lupa_button = customtkinter.CTkButton(
        lupa_frame, 
        image=lupa_ctk_image, 
        text="", 
        command=update_label, 
        fg_color="green", 
        width=120, 
        height=32
    )
    lupa_button.pack(side="left", padx=5)

    # Etiqueta para mostrar la carpeta seleccionada
    rounded_label = customtkinter.CTkLabel(
        lupa_frame, 
        text=program_state.get("backup_dir", ""), 
        font=("Arial", 12), 
        corner_radius=10, 
        fg_color="gray", 
        width=30
    )
    rounded_label.pack(side="left", padx=5, fill="x", expand=True)

    def schedule_backup_wrapper(h, m):
        schedule_backup(h, m)

    # Ahora definimos el botón de configuración avanzada
    advanced_settings_button = customtkinter.CTkButton(
        buttons_frame, 
        text="⚙ Configuración avanzada", 
        command=lambda: open_advance_options(root, rounded_label, schedule_backup_wrapper), 
        fg_color="DarkOrange3", 
        width=150
    )
    advanced_settings_button.pack(pady=5, anchor="e")

    # Botón para ejecutar respaldo
    execute_button = customtkinter.CTkButton(
        frame, 
        text="Ejecutar Respaldo", 
        command=lambda: execute_backup(
            rounded_label.cget("text"), 
            server_data, 
            AppState.backup_hours, 
            AppState.backup_minutes
        ), 
        fg_color="green"
    )
    execute_button.pack(pady=10)

    # # Botón para administrar usuarios
    # user_admin_button = customtkinter.CTkButton(
    #     buttons_frame, 
    #     text="👤 Administrar Usuarios", 
    #     command=lambda: open_user_management(root), 
    #     fg_color="DarkOrchid3", 
    #     width=150
    # )
    # user_admin_button.pack(pady=5, anchor="e")

    # Estado de programación - mostrar tareas configuradas
    schedule_status = "No programado"
    if backup_tasks:
        enabled_tasks = [t for t in backup_tasks if t.get("enabled", True)]
        if enabled_tasks:
            if len(enabled_tasks) == 1:
                task = enabled_tasks[0]
                if task["type"] == "frequency":
                    schedule_status = f"Programado: cada {task['hours']}h:{task['minutes']}m"
                else:
                    schedule_status = f"Programado: a las {str(task['hour']).zfill(2)}:{str(task['minute']).zfill(2)}"
            else:
                schedule_status = f"Programado: {len(enabled_tasks)} tarea(s)"
    
    schedule_label = customtkinter.CTkLabel(
        frame, 
        text=schedule_status,
        font=("Arial", 12, "italic")
    )
    schedule_label.pack(pady=5)

    # Variable para guardar la ruta de la carpeta
    folder_path = program_state.get("backup_dir", "")
    if folder_path:
        rounded_label.configure(text=folder_path)

    # Función para ejecutar respaldo
    def execute_backup(
        folder: str, 
        server_data: Dict[str, Any], 
        backup_hours: Optional[int], 
        backup_minutes: Optional[int]
    ) -> None:
        """Ejecuta un respaldo de la base de datos."""
        nonlocal folder_path
        
        # Prevenir ejecuciones múltiples usando AppState
        if AppState.backup_in_progress:
            logger.warning("Intento de ejecutar backup mientras otro está en progreso")
            messagebox.showwarning("Advertencia", "Ya hay un respaldo en progreso.")
            return
        
        folder_path = folder
        
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return
            
        # Verificar directorio
        try:
            if not os.path.isdir(folder_path):
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    logger.info(f"Directorio creado: {folder_path}")
                except Exception as e:
                    logger.error(f"Error al crear directorio: {e}")
                    messagebox.showerror("Error", f"No se pudo crear el directorio: {e}")
                    return
            
            # Verificar permisos escribiendo un archivo temporal
            check_file = os.path.join(folder_path, "check_write.tmp")
            try:
                with open(check_file, 'w') as f:
                    f.write("check")
                if os.path.exists(check_file):
                    os.unlink(check_file)
                logger.info(f"Permisos de escritura verificados en: {folder_path}")
            except Exception as perm_error:
                logger.error(f"Error de permisos de escritura: {perm_error}")
                messagebox.showerror("Error", f"No se tienen permisos de escritura en el directorio: {perm_error}")
                return
        except Exception as dir_error:
            logger.error(f"Error al verificar directorio: {dir_error}")
            messagebox.showerror("Error", f"Error al verificar el directorio: {dir_error}")
            return

        # Marcar que el backup está en progreso usando AppState
        AppState.backup_in_progress = True
        
        # Inicializar ConfigManager para usar sus métodos seguros
        config_manager = ConfigManager()

        # Creación de la ventana de progreso
        progress_window = customtkinter.CTkToplevel(root)
        progress_window.title("Realizando Respaldo")
        center_window(progress_window, 300, 100)
        progress_window.attributes('-topmost', True)
        progress_window.focus_force()

        # Marco para contener los elementos de la ventana de progreso
        progress_frame = customtkinter.CTkFrame(progress_window)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Usar ttk.Progressbar
        progressbar = ttk.Progressbar(progress_frame, mode='determinate', length=280)
        progressbar.pack(pady=10, padx=10)

        # Etiqueta para mostrar el estado currente
        progress_label = customtkinter.CTkLabel(progress_frame, text="Iniciando respaldo...")
        progress_label.pack(pady=5)

        # Forzar la actualización de la interfaz
        progress_window.update()

        def update_progress(value: int, text: str) -> None:
            """Actualiza la barra de progreso y el texto."""
            if progress_window.winfo_exists():
                progressbar['value'] = value
                progress_label.configure(text=text)
                progress_window.update_idletasks()
                progress_window.update()

        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                progress_window.destroy()
                return

            # Verificar si hay servidores configurados en servers.json
            enabled_servers = config_manager.get_enabled_servers()
            
            # Actualizar el estado del programa de manera segura usando ConfigManager
            config_manager.update_program_state(
                running=True,
                status="in_progress",
                backup_dir=folder_path,
                progress=0
            )

            # Definir funciones de completado y manejo de errores
            def completion_tasks(result=True) -> None:
                if not result:
                    handle_error(Exception("El proceso de respaldo falló."))
                    return
                    
                update_progress(100, "Respaldo completado.")
                
                # Liberar flag de backup en progreso usando AppState
                AppState.backup_in_progress = False
                
                # Actualizar estado de manera segura
                config_manager.update_program_state(
                    status="completed",
                    client=server_data.get("client", "Cliente"),
                    backup_dir=folder_path,
                    amount=AppState.selected_amount,
                    timestamp=datetime.datetime.now().isoformat(),
                    progress=100
                )
                
                if progress_window.winfo_exists():
                    progress_window.destroy()
                
                messagebox.showinfo("Éxito", "Respaldo completado con éxito.")
                
                # Configurar programación si se solicitó
                if backup_hours or backup_minutes:
                    # Programar respaldo con ConfigManager
                    config_manager.set_backup_schedule(
                        hours=backup_hours if backup_hours is not None else 4,
                        minutes=backup_minutes if backup_minutes is not None else 0,
                        enabled=True
                    )
                    
                    # Forzar guardado completo para asegurar que todos los campos están presentes
                    config_manager.force_save_all()
                    
                    ocultar_ventana()
                    
                    # Actualizar etiqueta de programación
                    schedule_label.configure(
                        text=f"Programado: cada {backup_hours}h:{backup_minutes}m"
                    )
                    
                    # Iniciar hilo de programación
                    if AppState.scheduled_backup_thread is None or not AppState.scheduled_backup_thread.is_alive():
                        AppState.scheduled_backup_thread = threading.Thread(
                            target=run_scheduler, 
                            daemon=True
                        )
                        AppState.scheduled_backup_thread.start()
                        
                    messagebox.showinfo(
                        "Info", 
                        f"Respaldo automático programado cada {backup_hours} horas y {backup_minutes} minutos."
                    )
                else:
                    messagebox.showinfo("Info", "Respaldo automático no programado.")
            
            def handle_error(e: Exception) -> None:
                # Liberar flag de backup en progreso usando AppState
                AppState.backup_in_progress = False
                
                config_manager.update_program_state(
                    status="error",
                    progress=0
                )
                
                if progress_window.winfo_exists():
                    progress_window.destroy()
                
                logger.error(f"Error en el respaldo: {e}", exc_info=True)
                messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")

            # Definir función de respaldo según modo
            if enabled_servers:
                # Modo Multi-Servidor: usar backup_all_servers()
                def run_backup() -> None:
                    try:
                        # Crear instancia de BackupManager
                        backup_manager = BackupManager()
                        
                        # El log se genera en backup_manager.backup_all_servers()
                        
                        # Wrapper para actualizar progreso en el hilo principal de manera segura
                        def safe_update_progress(value: int, text: str) -> None:
                            try:
                                if progress_window.winfo_exists():
                                    # Llamar directamente sin lambda para evitar bucles
                                    def do_update():
                                        update_progress(value, text)
                                    progress_window.after(0, do_update)
                            except Exception as e:
                                logger.warning(f"Error actualizando progreso: {e}")
                        
                        results = backup_manager.backup_all_servers(
                            folder_path,
                            AppState.selected_amount,
                            update_callback=safe_update_progress
                        )
                        
                        # Verificar resultados
                        successful = sum(1 for v in results.values() if v)
                        total = len(results)
                        result = successful > 0  # True si al menos uno fue exitoso
                        
                        # El log de completado ya se genera en backup_manager.backup_all_servers()
                        
                        # Actualizar al completar en el hilo principal
                        progress_window.after(0, lambda: completion_tasks(result))
                            
                    except Exception as e:
                        # Manejar errores en el hilo principal
                        progress_window.after(0, lambda: handle_error(e))
            else:
                # Modo Legado: usar server_data tradicional (compatibilidad hacia atrás)
                def run_backup() -> None:
                    try:
                        # Crear instancia de BackupManager
                        backup_manager = BackupManager()
                        
                        server_type = server_data.get("server_type")
                        # Ejecutar respaldo según el tipo de servidor
                        if server_type == "MySQL Server (TCP/IP)":
                            result = backup_manager.backup_mysql_database(
                                server_data["password"], 
                                folder_path, 
                                server_data.get("client", "Cliente"), 
                                AppState.selected_amount,
                                server_data,
                                update_callback=update_progress
                            )
                        elif server_type == "SQL Server (Windows Authentication)":
                            result = backup_manager.backup_sqlserver_database(
                                server_data,
                                folder_path,
                                server_data.get("client", "Cliente"),
                                AppState.selected_amount,
                                update_callback=update_progress
                            )
                        else:
                            result = False
                        
                        # Actualizar al completar en el hilo principal
                        progress_window.after(0, lambda: completion_tasks(result))
                    except Exception as e:
                        # Manejar errores en el hilo principal
                        progress_window.after(0, lambda: handle_error(e))
            
            # Iniciar el proceso de respaldo en un hilo separado
            backup_thread = threading.Thread(target=run_backup, daemon=True)
            backup_thread.start()
        except Exception as e:
            # Liberar flag de backup en progreso usando AppState
            AppState.backup_in_progress = False
            
            try:
                config_manager.update_program_state(
                    status="error",
                    progress=0
                )
            except:
                # Si falla el ConfigManager, intentamos con la función básica
                program_state["status"] = "error"
                save_state(STATUS_PROGRAM, program_state)
            
            if progress_window and progress_window.winfo_exists():
                progress_window.destroy()
            
            logger.error(f"Error general en respaldo: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")

    def schedule_backup(backup_hours: Optional[int], backup_minutes: Optional[int]) -> None:
        """Programa un respaldo automático (método legacy para compatibilidad)."""
        schedule_all_tasks()

    def schedule_all_tasks() -> None:
        """Programa todas las tareas de respaldo configuradas."""
        # Obtener estado actual para asegurar que tenemos valores válidos
        current_folder_path = folder_path
        current_server_data = server_data.copy() if server_data else None
        
        if not current_folder_path or not current_server_data:
            logger.error("No se puede programar respaldo: faltan datos de ruta o servidor")
            return
        
        # Limpiar programaciones anteriores
        schedule.clear()
        
        # Obtener tareas configuradas
        from config_manager import ConfigManager
        config_manager = ConfigManager()
        backup_tasks = config_manager.get_backup_tasks()
        
        if not backup_tasks:
            logger.warning("No hay tareas de respaldo configuradas")
            return
        
        # Función de respaldo que captura el estado actual
        def run_backup_task():
            logger.info("Ejecutando tarea programada de respaldo")
            return execute_programed_backup(current_folder_path, current_server_data)
        
        # Programar cada tarea
        tasks_scheduled = 0
        for idx, task in enumerate(backup_tasks, 1):
            if not task.get("enabled", True):
                logger.info(f"Tarea {idx} deshabilitada, omitiendo")
                continue
            
            task_type = task.get("type")
            
            if task_type == "frequency":
                hours = task.get("hours", 0)
                minutes = task.get("minutes", 0)
                interval_seconds = (hours * 3600) + (minutes * 60)
                
                if interval_seconds > 0:
                    job = schedule.every(interval_seconds).seconds.do(run_backup_task)
                    job.tag("backup_task")
                    logger.info(f"Tarea {idx} (frecuencia): cada {hours}h:{minutes}m programada")
                    tasks_scheduled += 1
                    
                    # Actualizar AppState con la primera tarea de frecuencia
                    if tasks_scheduled == 1:
                        AppState.set_backup_time(hours, minutes)
                        
            elif task_type == "fixed_time":
                hour = task.get("hour", 0)
                minute = task.get("minute", 0)
                time_str = f"{str(hour).zfill(2)}:{str(minute).zfill(2)}"
                
                job = schedule.every().day.at(time_str).do(run_backup_task)
                job.tag("backup_task")
                logger.info(f"Tarea {idx} (hora fija): a las {time_str} programada")
                tasks_scheduled += 1
        
        if tasks_scheduled > 0:
            AppState.set_scheduled(True)
            logger.info(f"Respaldos programados: {tasks_scheduled} tarea(s)")
            
            # Iniciar thread si no está activo
            if AppState.scheduled_backup_thread is None or not AppState.scheduled_backup_thread.is_alive():
                AppState.scheduled_backup_thread = threading.Thread(
                    target=run_scheduler, 
                    daemon=True
                )
                AppState.scheduled_backup_thread.start()
                logger.info("Thread de respaldos programados iniciado")
        else:
            logger.warning("No se programaron tareas de respaldo")
    
    def run_scheduler() -> None:
        """Ejecuta el programador de tareas."""
        logger.info("Iniciando programador de respaldos")
        
        try:
            # Verificar que hay tareas programadas
            jobs = list(schedule.jobs)
            if not jobs:
                logger.warning("No hay tareas programadas al iniciar run_scheduler")
                
                # Intentar recuperar configuración y reprogramar
                schedule_all_tasks()
            
            # Bucle principal
            while AppState.running and AppState.scheduled:
                schedule.run_pending()
                
                # Verificar periódicamente si hay tareas
                if not schedule.jobs:
                    logger.warning("No hay tareas programadas durante la ejecución")
                    schedule_all_tasks()
                
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error en programador de respaldos: {e}", exc_info=True)
            
        logger.info("Programador de respaldos detenido")

    def execute_programed_backup(folder_path: str, server_data: Dict[str, Any]) -> None:
        """Ejecuta un respaldo programado."""
        try:
            if not AppState.running or not AppState.scheduled:
                return
                
            logger.info(f"Ejecutando respaldo programado en {folder_path}")
            
            if server_data is None:
                logger.error("No se recibieron los datos del servidor para respaldo programado")
                return
                
            server_type = server_data.get("server_type")
            if server_type in ["MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"]:
                # Verificar que el directorio existe
                if not os.path.exists(folder_path):
                    try:
                        os.makedirs(folder_path, exist_ok=True)
                        logger.info(f"Directorio de respaldo creado: {folder_path}")
                    except Exception as dir_error:
                        logger.error(f"Error al crear directorio de respaldo: {dir_error}")
                        send_email(server_data.get("client", "Cliente"), 
                                f"Error al crear directorio de respaldo: {dir_error}")
                        return
                        
                # Verificar permisos
                try:
                    check_file = os.path.join(folder_path, "check_write.tmp")
                    with open(check_file, 'w') as f:
                        f.write("check")
                    if os.path.exists(check_file):
                        os.remove(check_file)
                    logger.info("Permisos de escritura verificados en directorio de respaldo")
                except Exception as perm_error:
                    logger.error(f"Error de permisos en directorio de respaldo: {perm_error}")
                    send_email(server_data.get("client", "Cliente"), 
                            f"Error de permisos en directorio de respaldo: {perm_error}")
                    return
                
                # Crear instancia de BackupManager para el respaldo programado
                backup_manager = BackupManager()
                
                # Ejecutar respaldo según el tipo
                if server_type == "MySQL Server (TCP/IP)":
                    result = backup_manager.backup_mysql_database(
                        server_data["password"], 
                        folder_path, 
                        server_data.get("client", "Cliente"), 
                        AppState.selected_amount,
                        server_data
                    )
                elif server_type == "SQL Server (Windows Authentication)":
                    result = backup_manager.backup_sqlserver_database(
                        server_data,
                        folder_path,
                        server_data.get("client", "Cliente"),
                        AppState.selected_amount
                    )
                else:
                    result = False
                
                if result:
                    logger.info("Respaldo programado completado con éxito")
                else:
                    logger.error("Respaldo programado completado con errores")
            else:
                logger.error(f"Tipo de servidor no soportado para respaldo programado: {server_type}")
                message = f"Tipo de servidor no soportado para respaldo programado: {server_type}"
                send_email(server_data.get("client", "Cliente"), message)
        except Exception as e:
            logger.error(f"Error al ejecutar el respaldo automático: {e}", exc_info=True)
            message = f"Error al ejecutar el respaldo automático: {e}"
            send_email(server_data.get("client", "Cliente"), message)

    def ocultar_ventana() -> None:
        """Oculta la ventana principal y muestra un ícono en la bandeja del sistema."""
        root.withdraw()
        create_system_tray_icon()
    
    def show_backup_history(label_widget: customtkinter.CTkLabel) -> None:
        """Muestra el historial de respaldos realizados, agrupados por servidor."""
        if "history_window" in active_windows and active_windows["history_window"].winfo_exists():
            active_windows["history_window"].lift()
            active_windows['history_window'].focus_force()
            return
        
        try:
            backup_dir = label_widget.cget("text")
            if not backup_dir:
                raise ValueError("No se ha seleccionado un directorio de respaldos.")
                
            if not os.path.exists(backup_dir):
                raise ValueError("El directorio de respaldos no existe.")
            
            # Obtener información de servidores configurados
            servers_info = {}
            try:
                enabled_servers = config_manager.get_servers()
                for server in enabled_servers:
                    server_id = server.get("id", "")
                    server_name = server.get("name", server.get("client", server_id))
                    servers_info[server_id] = server_name
            except Exception:
                pass
            
            # Estructura para almacenar respaldos por servidor
            backups_by_server = {}
            
            # Buscar subcarpetas de servidor (server_1, server_2, etc.)
            server_folders = []
            root_backup_files = []
            
            for entry in os.scandir(backup_dir):
                if entry.is_dir() and entry.name.startswith("server_"):
                    server_folders.append(entry)
                elif entry.is_file() and entry.name.endswith(".7z"):
                    root_backup_files.append(entry.path)
            
            # Procesar carpetas de servidor
            for server_folder in server_folders:
                server_id = server_folder.name
                server_name = servers_info.get(server_id, server_id)
                
                server_backups = [
                    entry.path for entry in os.scandir(server_folder.path) 
                    if entry.is_file() and entry.name.endswith(".7z")
                ]
                
                if server_backups:
                    server_backups.sort(key=os.path.getmtime, reverse=True)
                    backups_by_server[server_id] = {
                        "name": server_name,
                        "files": server_backups
                    }
            
            # Procesar archivos en la raíz (modo legacy o servidor único)
            if root_backup_files:
                root_backup_files.sort(key=os.path.getmtime, reverse=True)
                backups_by_server["_root"] = {
                    "name": "General",
                    "files": root_backup_files
                }
            
            if not backups_by_server:
                raise ValueError("No hay respaldos disponibles en el directorio seleccionado.")
            
            # Mostrar en ventana de diálogo
            history_window = customtkinter.CTkToplevel(root)
            active_windows["history_window"] = history_window
            history_window.title("Historial de Respaldos")
            center_window(history_window, 700, 500)
            
            history_frame = customtkinter.CTkFrame(history_window)
            history_frame.pack(pady=10, padx=10, fill="both", expand=True)
            history_window.transient(root)
            history_window.grab_set()
            
            title_label = customtkinter.CTkLabel(
                history_frame, 
                text="Historial de Respaldos", 
                font=("Arial", 16, "bold")
            )
            title_label.pack(pady=10)
            
            # Info del total de servidores
            total_servers = len([k for k in backups_by_server.keys() if k != "_root"])
            total_backups = sum(len(data["files"]) for data in backups_by_server.values())
            
            info_text = f"📁 {total_backups} respaldo(s)"
            if total_servers > 0:
                info_text += f" en {total_servers} servidor(es)"
            
            info_label = customtkinter.CTkLabel(
                history_frame,
                text=info_text,
                font=("Arial", 11),
                text_color="gray"
            )
            info_label.pack(pady=(0, 5))
            
            # Crear scrollable frame para la lista
            scrollable_frame = customtkinter.CTkScrollableFrame(history_frame)
            scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Ordenar servidores: primero los server_X, luego _root
            sorted_servers = sorted(
                backups_by_server.keys(),
                key=lambda x: (x == "_root", x)
            )
            
            # Añadir items agrupados por servidor
            for server_id in sorted_servers:
                server_data = backups_by_server[server_id]
                server_name = server_data["name"]
                server_files = server_data["files"]
                
                # Header del servidor
                if len(backups_by_server) > 1 or server_id != "_root":
                    header_frame = customtkinter.CTkFrame(scrollable_frame, fg_color="transparent")
                    header_frame.pack(fill="x", pady=(10, 5))
                    
                    display_name = server_name if server_id == "_root" else f"🖥️ {server_name}"
                    if server_id != "_root" and server_id != server_name:
                        display_name += f" ({server_id})"
                    
                    header_label = customtkinter.CTkLabel(
                        header_frame,
                        text=f"{display_name} — {len(server_files)} respaldo(s)",
                        font=("Arial", 13, "bold"),
                        anchor="w"
                    )
                    header_label.pack(side="left", fill="x", padx=5)
                
                # Lista de archivos de este servidor
                for backup_file in server_files:
                    item_frame = customtkinter.CTkFrame(scrollable_frame)
                    item_frame.pack(fill="x", pady=2, padx=(20 if len(backups_by_server) > 1 else 0, 0))
                    
                    file_name = os.path.basename(backup_file)
                    file_date = datetime.datetime.fromtimestamp(
                        os.path.getmtime(backup_file)
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    file_size = os.path.getsize(backup_file)
                    
                    # Formatear tamaño
                    if file_size >= 1024 * 1024 * 1024:
                        size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
                    elif file_size >= 1024 * 1024:
                        size_str = f"{file_size / (1024 * 1024):.1f} MB"
                    elif file_size >= 1024:
                        size_str = f"{file_size / 1024:.1f} KB"
                    else:
                        size_str = f"{file_size} B"
                    
                    item_label = customtkinter.CTkLabel(
                        item_frame,
                        text=f"📦 {file_name}",
                        anchor="w",
                        font=("Arial", 11)
                    )
                    item_label.pack(side="left", fill="x", expand=True, padx=5)
                    
                    details_label = customtkinter.CTkLabel(
                        item_frame,
                        text=f"{size_str}  •  {file_date}",
                        anchor="e",
                        font=("Arial", 10),
                        text_color="gray"
                    )
                    details_label.pack(side="right", padx=5)

            def on_history_close() -> None:
                """Maneja el cierre de la ventana de historial."""
                active_windows.pop("history_window", None)
                history_window.destroy() 

            close_button = customtkinter.CTkButton(
                history_frame,
                text="Cerrar",
                command=on_history_close,
                fg_color="gray"
            )
            close_button.pack(pady=10)

            history_window.protocol("WM_DELETE_WINDOW", on_history_close)           
            
        except ValueError as ve:
            messagebox.showinfo("Historial de Respaldos", str(ve))
        except Exception as e:
            logger.error(f"Error al obtener el historial de respaldos: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error al obtener el historial de respaldos: {e}")

    # Manejo del cierre de la ventana
    def on_closing() -> None:
        """Maneja el cierre de la ventana principal."""
        if AppState.scheduled:
            if not messagebox.askyesno(
                "Confirmar salida", 
                "Hay respaldos programados en ejecución. ¿Desea cerrar la aplicación?"
            ):
                return
        
        AppState.running = False
        AppState.scheduled = False
        
        if AppState.app_icon:
            AppState.app_icon.stop()
            
        # Usar ConfigManager para actualizar solo los campos necesarios sin perder configuración
        try:
            from config_manager import ConfigManager
            cm = ConfigManager()
            cm.update_program_state(
                running=False,
                status="stopped"
            )
            logger.info("Estado guardado correctamente al cerrar la aplicación")
        except Exception as e:
            logger.error(f"Error al guardar estado al cerrar: {e}")
        
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def open_task_assignment_window(parent_window: customtkinter.CTk, on_save_callback: Optional[Callable] = None) -> None:
    """
    Abre la ventana de asignación de tareas de respaldo.
    
    Args:
        parent_window: Ventana padre
        on_save_callback: Función a llamar cuando se guarden las tareas
    """
    from config_manager import ConfigManager
    config_manager = ConfigManager()
    
    # Crear ventana
    task_window = customtkinter.CTkToplevel(parent_window)
    task_window.title("Asignar Tareas de Respaldo")
    task_window.configure(fg_color=("#2b2b2b", "#2b2b2b"))
    task_window.transient(parent_window)
    task_window.grab_set()
    center_window(task_window, 600, 450)
    task_window.after(10, lambda: task_window.focus_force())
    
    # Frame principal
    main_frame = customtkinter.CTkFrame(task_window)
    main_frame.pack(pady=15, padx=15, fill="both", expand=True)
    
    # Título
    title_label = customtkinter.CTkLabel(
        main_frame,
        text="Configuración de Tareas Programadas",
        font=("Roboto", 18, "bold")
    )
    title_label.pack(pady=(15, 5))
    
    # Descripción
    desc_label = customtkinter.CTkLabel(
        main_frame,
        text="Puede configurar hasta 3 tareas de respaldo.\nTipo 'Frecuencia': ejecuta cada X tiempo. Tipo 'Hora Fija': ejecuta a una hora específica.",
        font=("Roboto", 12),
        text_color="gray"
    )
    desc_label.pack(pady=(0, 15))
    
    # Frame scrollable para las tareas
    tasks_container = customtkinter.CTkScrollableFrame(main_frame, height=180)
    tasks_container.pack(pady=5, padx=10, fill="both", expand=True)
    
    # Lista para almacenar los widgets de tareas
    task_widgets = []
    
    def validate_number(value, max_val):
        """Valida que el valor sea un número dentro del rango."""
        if value == "":
            return True
        try:
            num = int(value)
            return 0 <= num <= max_val
        except ValueError:
            return False
    
    def create_task_widget(task_data: Optional[dict] = None) -> customtkinter.CTkFrame:
        """Crea un widget para una tarea individual."""
        if len(task_widgets) >= 3:
            messagebox.showwarning("Límite alcanzado", "No se pueden agregar más de 3 tareas.")
            return None
        
        task_frame = customtkinter.CTkFrame(tasks_container)
        task_frame.pack(pady=8, padx=5, fill="x")
        
        # Número de tarea
        task_num = len(task_widgets) + 1
        num_label = customtkinter.CTkLabel(task_frame, text=f"Tarea {task_num}:", font=("Roboto", 13, "bold"), width=80)
        num_label.pack(side="left", padx=(10, 5))
        
        # Mapeo de tipos
        type_display = {"frequency": "Frecuencia", "fixed_time": "Hora Fija"}
        type_values = {"Frecuencia": "frequency", "Hora Fija": "fixed_time"}
        
        # Determinar valores iniciales
        initial_type = task_data.get("type", "frequency") if task_data else "frequency"
        initial_display = type_display.get(initial_type, "Frecuencia")
        
        if initial_type == "frequency":
            initial_hour = str(task_data.get("hours", 0)) if task_data else "0"
            initial_minute = str(task_data.get("minutes", 10)) if task_data else "10"
        else:
            initial_hour = str(task_data.get("hour", 12)).zfill(2) if task_data else "12"
            initial_minute = str(task_data.get("minute", 0)).zfill(2) if task_data else "00"
        
        # Variables para los valores - inicializadas con los datos
        hour_var = customtkinter.StringVar(value=initial_hour)
        minute_var = customtkinter.StringVar(value=initial_minute)
        enabled_var = customtkinter.BooleanVar(value=task_data.get("enabled", True) if task_data else True)
        
        current_type = {"value": initial_type}
        
        # Tipo de tarea (con nombres legibles)
        type_combo = customtkinter.CTkComboBox(
            task_frame,
            values=["Frecuencia", "Hora Fija"],
            width=120,
            font=("Roboto", 12),
            state="readonly"
        )
        type_combo.pack(side="left", padx=5)
        type_combo.set(initial_display)
        
        # Frame para los campos de tiempo (cambia según el tipo)
        time_frame = customtkinter.CTkFrame(task_frame, fg_color="transparent")
        time_frame.pack(side="left", padx=5, fill="x", expand=True)
        
        def get_actual_type():
            """Obtiene el tipo real basado en el display."""
            display_val = type_combo.get()
            return type_values.get(display_val, "frequency")
        
        def update_time_fields(new_type=None):
            """Actualiza los campos según el tipo seleccionado."""
            # Limpiar campos anteriores
            for widget in time_frame.winfo_children():
                widget.destroy()
            
            actual_type = get_actual_type()
            
            # Si cambió el tipo, resetear valores apropiados
            if new_type is not None:
                if actual_type == "frequency":
                    hour_var.set("0")
                    minute_var.set("10")
                else:
                    hour_var.set("12")
                    minute_var.set("00")
            
            if actual_type == "frequency":
                # Campos para frecuencia: Horas y Minutos de intervalo
                h_label = customtkinter.CTkLabel(time_frame, text="Cada:", font=("Roboto", 12))
                h_label.pack(side="left", padx=(0, 5))
                
                hour_entry = customtkinter.CTkEntry(
                    time_frame,
                    textvariable=hour_var,
                    width=50,
                    font=("Roboto", 12),
                    justify="center"
                )
                hour_entry.pack(side="left", padx=2)
                
                h_label2 = customtkinter.CTkLabel(time_frame, text="h", font=("Roboto", 12))
                h_label2.pack(side="left", padx=(0, 8))
                
                min_entry = customtkinter.CTkEntry(
                    time_frame,
                    textvariable=minute_var,
                    width=50,
                    font=("Roboto", 12),
                    justify="center"
                )
                min_entry.pack(side="left", padx=2)
                
                m_label = customtkinter.CTkLabel(time_frame, text="m", font=("Roboto", 12))
                m_label.pack(side="left")
                    
            else:  # fixed_time
                # Campos para hora fija: Hora específica del día
                h_label = customtkinter.CTkLabel(time_frame, text="A las:", font=("Roboto", 12))
                h_label.pack(side="left", padx=(0, 5))
                
                hour_entry = customtkinter.CTkEntry(
                    time_frame,
                    textvariable=hour_var,
                    width=50,
                    font=("Roboto", 12),
                    justify="center"
                )
                hour_entry.pack(side="left", padx=2)
                
                sep_label = customtkinter.CTkLabel(time_frame, text=":", font=("Roboto", 14, "bold"))
                sep_label.pack(side="left")
                
                min_entry = customtkinter.CTkEntry(
                    time_frame,
                    textvariable=minute_var,
                    width=50,
                    font=("Roboto", 12),
                    justify="center"
                )
                min_entry.pack(side="left", padx=2)
                
                hrs_label = customtkinter.CTkLabel(time_frame, text="hrs", font=("Roboto", 11), text_color="gray")
                hrs_label.pack(side="left", padx=(3, 0))
        
        # Checkbox habilitado
        enabled_check = customtkinter.CTkCheckBox(
            task_frame,
            text="",
            variable=enabled_var,
            width=24,
            checkbox_width=20,
            checkbox_height=20
        )
        enabled_check.pack(side="left", padx=8)
        
        # Guardar referencia antes de crear el botón eliminar
        task_info = {
            "frame": task_frame,
            "num_label": num_label,
            "type_combo": type_combo,
            "type_values": type_values,
            "time_frame": time_frame,
            "hour_var": hour_var,
            "minute_var": minute_var,
            "enabled_var": enabled_var
        }
        
        # Botón eliminar
        def remove_task():
            task_widgets.remove(task_info)
            task_frame.destroy()
            # Renumerar tareas restantes
            for i, tw in enumerate(task_widgets):
                tw["num_label"].configure(text=f"Tarea {i+1}:")
            update_info_label()
        
        remove_btn = customtkinter.CTkButton(
            task_frame,
            text="✕",
            width=32,
            height=32,
            font=("Roboto", 14),
            fg_color="#dc3545",
            hover_color="#c82333",
            command=remove_task
        )
        remove_btn.pack(side="right", padx=8)
        
        # Vincular cambio de tipo - pasar argumento para indicar que es un cambio manual
        type_combo.configure(command=lambda x: update_time_fields(x))
        
        # Inicializar campos sin resetear valores
        update_time_fields()
        
        task_widgets.append(task_info)
        
        return task_frame
    
    # Cargar tareas existentes
    existing_tasks = config_manager.get_backup_tasks()
    for task in existing_tasks:
        create_task_widget(task)
    
    # Si no hay tareas, crear una por defecto
    if not task_widgets:
        create_task_widget({"type": "frequency", "hours": 4, "minutes": 0, "enabled": True})
    
    # Frame para botones de acción
    action_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
    action_frame.pack(pady=10, fill="x")
    
    # Etiqueta informativa
    info_label = customtkinter.CTkLabel(
        action_frame,
        text=f"({len(task_widgets)}/3 tareas)",
        font=("Roboto", 12),
        text_color="gray"
    )
    info_label.pack(side="right", padx=15)
    
    def update_info_label():
        info_label.configure(text=f"({len(task_widgets)}/3 tareas)")
    
    # Botón añadir tarea
    def add_new_task():
        create_task_widget()
        update_info_label()
    
    add_btn = customtkinter.CTkButton(
        action_frame,
        text="+ Añadir Tarea",
        width=130,
        height=32,
        font=("Roboto", 13),
        fg_color="#28a745",
        hover_color="#218838",
        command=add_new_task
    )
    add_btn.pack(side="left", padx=15)
    
    # Frame para botones guardar/cancelar
    button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=15, fill="x", side="bottom")
    
    def save_tasks():
        """Guarda las tareas configuradas."""
        tasks = []
        for tw in task_widgets:
            display_val = tw["type_combo"].get()
            task_type = tw["type_values"].get(display_val, "frequency")
            enabled = tw["enabled_var"].get()
            
            time_frame = tw["time_frame"]
            entries = [child for child in time_frame.winfo_children() 
                      if isinstance(child, customtkinter.CTkEntry)]
            
            if len(entries) < 2:
                messagebox.showerror("Error", "No se encontraron los campos de tiempo.", parent=task_window)
                task_window.lift()
                task_window.focus_force()
                return
            
            try:
                hour_val = entries[0].get().strip() or "0"
                minute_val = entries[1].get().strip() or "0"
                
                if task_type == "frequency":
                    hours = int(hour_val)
                    minutes = int(minute_val)
                    
                    if hours == 0 and minutes == 0:
                        messagebox.showwarning("Advertencia", "La frecuencia no puede ser 0 horas y 0 minutos.", parent=task_window)
                        task_window.lift()
                        task_window.focus_force()
                        return
                    
                    if hours < 0 or hours > 24:
                        messagebox.showwarning("Advertencia", "Las horas deben estar entre 0 y 24.", parent=task_window)
                        task_window.lift()
                        task_window.focus_force()
                        return
                    
                    if minutes < 0 or minutes > 59:
                        messagebox.showwarning("Advertencia", "Los minutos deben estar entre 0 y 59.", parent=task_window)
                        task_window.lift()
                        task_window.focus_force()
                        return
                    
                    tasks.append({
                        "type": "frequency",
                        "hours": hours,
                        "minutes": minutes,
                        "enabled": enabled
                    })
                else:  # fixed_time
                    hour = int(hour_val)
                    minute = int(minute_val)
                    
                    if hour < 0 or hour > 23:
                        messagebox.showwarning("Advertencia", "La hora debe estar entre 0 y 23.", parent=task_window)
                        task_window.lift()
                        task_window.focus_force()
                        return
                    
                    if minute < 0 or minute > 59:
                        messagebox.showwarning("Advertencia", "Los minutos deben estar entre 0 y 59.", parent=task_window)
                        task_window.lift()
                        task_window.focus_force()
                        return
                    
                    tasks.append({
                        "type": "fixed_time",
                        "hour": hour,
                        "minute": minute,
                        "enabled": enabled
                    })
            except ValueError as e:
                messagebox.showerror("Error", f"Ingrese solo números válidos en los campos de tiempo.", parent=task_window)
                task_window.lift()
                task_window.focus_force()
                return
        
        if not tasks:
            messagebox.showwarning("Advertencia", "Debe configurar al menos una tarea.", parent=task_window)
            task_window.lift()
            task_window.focus_force()
            return
        
        # Guardar tareas
        if config_manager.set_backup_tasks(tasks):
            logger.info(f"Tareas guardadas: {tasks}")
            messagebox.showinfo("Éxito", f"Se guardaron {len(tasks)} tarea(s) correctamente.", parent=task_window)
            
            if on_save_callback:
                on_save_callback(tasks)
            
            task_window.destroy()
        else:
            messagebox.showerror("Error", "No se pudieron guardar las tareas.", parent=task_window)
            task_window.lift()
            task_window.focus_force()
    
    def cancel():
        task_window.destroy()
    
    save_btn = customtkinter.CTkButton(
        button_frame,
        text="Guardar Tareas",
        width=130,
        height=36,
        font=("Roboto", 13),
        fg_color="#007bff",
        hover_color="#0056b3",
        command=save_tasks
    )
    save_btn.pack(side="left", padx=15)
    
    cancel_btn = customtkinter.CTkButton(
        button_frame,
        text="Cancelar",
        width=110,
        height=36,
        font=("Roboto", 13),
        fg_color="#6c757d",
        hover_color="#5a6268",
        command=cancel
    )
    cancel_btn.pack(side="left", padx=5)
    
    task_window.mainloop()

def open_advance_options(parent_window: customtkinter.CTk, rounded_label: customtkinter.CTkLabel, schedule_func: Optional[Callable] = None) -> None:
    """Abre la ventana de opciones avanzadas con diseño mejorado."""
    from config_manager import ConfigManager
    config_manager = ConfigManager()
    
    # Crear ventana de configuración
    root = customtkinter.CTk()
    root.title("Configuración Avanzada")
    center_window(root, 480, 550)

    # Frame principal
    main_frame = customtkinter.CTkFrame(root)
    main_frame.pack(pady=15, padx=20, fill="both", expand=True)

    # Título
    title_label = customtkinter.CTkLabel(
        main_frame, 
        text="Configuración Avanzada", 
        font=("Roboto", 18, "bold")
    )
    title_label.pack(pady=(15, 20))

    # ========== Sección: Tareas Programadas ==========
    tasks_section = customtkinter.CTkFrame(main_frame)
    tasks_section.pack(pady=10, padx=15, fill="x")
    
    tasks_header = customtkinter.CTkLabel(
        tasks_section,
        text="📅 Tareas de Respaldo Programadas",
        font=("Roboto", 14, "bold"),
        anchor="w"
    )
    tasks_header.pack(pady=(10, 5), padx=10, anchor="w")
    
    # Mostrar resumen de tareas actuales
    tasks = config_manager.get_backup_tasks()
    if tasks:
        tasks_summary = ""
        for i, task in enumerate(tasks, 1):
            status_icon = "✓" if task.get("enabled", True) else "○"
            if task["type"] == "frequency":
                tasks_summary += f"  {status_icon} Tarea {i} [Frecuencia]: Cada {task['hours']}h:{task['minutes']}m\n"
            else:
                tasks_summary += f"  {status_icon} Tarea {i} [Hora Fija]: A las {str(task['hour']).zfill(2)}:{str(task['minute']).zfill(2)}\n"
    else:
        tasks_summary = "  No hay tareas configuradas"
    
    tasks_info = customtkinter.CTkLabel(
        tasks_section,
        text=tasks_summary,
        font=("Roboto", 12),
        anchor="w",
        justify="left"
    )
    tasks_info.pack(pady=5, padx=15, anchor="w")
    
    # Botón para abrir ventana de tareas
    def open_tasks():
        def on_tasks_saved(new_tasks):
            # Actualizar resumen
            if new_tasks:
                summary = ""
                for i, task in enumerate(new_tasks, 1):
                    status_icon = "✓" if task.get("enabled", True) else "○"
                    if task["type"] == "frequency":
                        summary += f"  {status_icon} Tarea {i} [Frecuencia]: Cada {task['hours']}h:{task['minutes']}m\n"
                    else:
                        summary += f"  {status_icon} Tarea {i} [Hora Fija]: A las {str(task['hour']).zfill(2)}:{str(task['minute']).zfill(2)}\n"
            else:
                summary = "  No hay tareas configuradas"
            tasks_info.configure(text=summary)
            
            # Activar programación si hay tareas
            if new_tasks and schedule_func:
                freq_tasks = [t for t in new_tasks if t["type"] == "frequency" and t.get("enabled", True)]
                if freq_tasks:
                    AppState.set_backup_time(freq_tasks[0]["hours"], freq_tasks[0]["minutes"])
                    AppState.set_scheduled(True)
        
        open_task_assignment_window(root, on_tasks_saved)
    
    assign_btn = customtkinter.CTkButton(
        tasks_section,
        text="Asignar Tareas",
        width=140,
        height=34,
        font=("Roboto", 13),
        fg_color="#007bff",
        hover_color="#0056b3",
        command=open_tasks
    )
    assign_btn.pack(pady=10, padx=15, anchor="e")

    # ========== Sección: Cantidad de Respaldos ==========
    amount_section = customtkinter.CTkFrame(main_frame)
    amount_section.pack(pady=10, padx=15, fill="x")
    
    amount_header = customtkinter.CTkLabel(
        amount_section,
        text="📁 Cantidad Máxima de Respaldos",
        font=("Roboto", 14, "bold"),
        anchor="w"
    )
    amount_header.pack(pady=(10, 5), padx=10, anchor="w")
    
    amount_desc = customtkinter.CTkLabel(
        amount_section,
        text="Número máximo de archivos de respaldo a conservar por servidor:",
        font=("Roboto", 12),
        text_color="gray",
        anchor="w"
    )
    amount_desc.pack(pady=(0, 5), padx=15, anchor="w")
    
    # Control de cantidad
    current_amount = config_manager.get_program_state().get("amount", 5)
    if current_amount is None or current_amount < 1:
        current_amount = 5
    
    spinbox_frame = customtkinter.CTkFrame(amount_section, fg_color="transparent")
    spinbox_frame.pack(pady=10, padx=15)

    def get_current_amount():
        """Obtiene el valor actual como entero directamente del Entry."""
        try:
            val = numeric_entry.get().strip()
            if not val:
                return 5
            return max(1, min(100, int(val)))
        except (ValueError, TypeError):
            return 5

    def decrease_value():
        val = get_current_amount()
        new_val = max(1, val - 1)
        numeric_entry.delete(0, "end")
        numeric_entry.insert(0, str(new_val))

    def increase_value():
        val = get_current_amount()
        new_val = min(100, val + 1)
        numeric_entry.delete(0, "end")
        numeric_entry.insert(0, str(new_val))

    decrease_button = customtkinter.CTkButton(
        spinbox_frame, text="−", width=44, height=36, 
        font=("Roboto", 18, "bold"),
        fg_color="#dc3545", hover_color="#c82333",
        command=decrease_value
    )
    decrease_button.pack(side="left", padx=5)

    numeric_entry = customtkinter.CTkEntry(
        spinbox_frame, width=70, height=36,
        font=("Roboto", 14), justify="center"
    )
    numeric_entry.pack(side="left", padx=5)
    numeric_entry.insert(0, str(current_amount))

    increase_button = customtkinter.CTkButton(
        spinbox_frame, text="+", width=44, height=36,
        font=("Roboto", 18, "bold"),
        fg_color="#28a745", hover_color="#218838",
        command=increase_value
    )
    increase_button.pack(side="left", padx=5)

    # ========== Botón Guardar (al final) ==========
    def save_advanced_settings():
        """Guarda la configuración avanzada."""
        try:
            selected_amount = get_current_amount()
            if selected_amount <= 0:
                selected_amount = 5
                numeric_entry.delete(0, "end")
                numeric_entry.insert(0, "5")
            
            AppState.set_amount(selected_amount)
            
            # Verificar directorio de destino
            folder_path = rounded_label.cget("text")
            if not folder_path or folder_path == "Seleccionar carpeta...":
                raise ValueError("No se ha seleccionado ninguna carpeta de destino.")
            
            # Guardar configuración
            config_manager.update_program_state(
                amount=selected_amount,
                backup_dir=folder_path
            )
            
            logger.info(f"Configuración guardada: amount={selected_amount}, backup_dir={folder_path}")
            messagebox.showinfo("Éxito", "Configuración guardada correctamente.", parent=root)
            root.destroy()
            parent_window.deiconify()
            parent_window.lift()
            parent_window.focus_force()

        except ValueError as e:
            messagebox.showerror("Error", f"Error en la configuración: {e}", parent=root)
            root.lift()
            root.focus_force()
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error al guardar: {e}", parent=root)
            root.lift()
            root.focus_force()

    # Frame para botón guardar
    button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(pady=15, fill="x", side="bottom")
    
    save_button = customtkinter.CTkButton(
        button_frame,
        text="Guardar Configuración",
        width=200,
        height=42,
        fg_color="#28a745",
        hover_color="#218838",
        font=("Roboto", 14, "bold"),
        command=save_advanced_settings
    )
    save_button.pack(pady=15)

    # Manejo del cierre
    def on_closing():
        root.destroy()
        parent_window.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def open_user_management(parent_window: customtkinter.CTk) -> None:
    """Abre la ventana de gestión de usuarios."""
    # Verificar si ya existe una ventana de gestión de usuarios abierta
    if 'user_management_window' in active_windows and active_windows['user_management_window'].winfo_exists():
        # Si existe, darle foco
        active_windows['user_management_window'].lift()
        active_windows['user_management_window'].focus_force()
        return
    
    try:        
        def on_close():
            active_windows.pop('user_management_window', None)
        
        # Crear ventana de gestión de usuarios
        user_mgmt = UserManagementWindow(parent_window, close_callback=on_close)
        active_windows['user_management_window'] = user_mgmt.window
        
    except Exception as e:
        logger.error(f"Error al abrir ventana de gestión de usuarios: {e}", exc_info=True)
        messagebox.showerror("Error", f"No se pudo abrir la gestión de usuarios: {e}")

def create_system_tray_icon() -> None:
    """Crea un ícono en la bandeja del sistema."""
    def show_window(icon, item) -> None:
        """Muestra la ventana principal."""
        if AppState.root_window:
            AppState.root_window.deiconify()
            AppState.root_window.lift()
            AppState.root_window.focus_force()
    
    def exit_app(icon, item) -> None:
        """Cierra la aplicación desde la bandeja del sistema."""
        # Usar ConfigManager para actualizar solo los campos necesarios sin perder configuración
        try:
            from config_manager import ConfigManager
            cm = ConfigManager()
            cm.update_program_state(
                running=False,
                status="stopped"
            )
            logger.info("Estado guardado correctamente al cerrar desde bandeja")
        except Exception as e:
            logger.error(f"Error al guardar estado al cerrar desde bandeja: {e}")
        
        # Detener programador y threads (solo en memoria, no en archivo)
        AppState.running = False
        AppState.scheduled = False
        
        # Detener ícono y cerrar ventana
        icon.stop()
        if AppState.root_window:
            AppState.root_window.destroy()
    
    # Crear menú para el ícono
    menu = (
        pystray.MenuItem('Mostrar Sistema de Respaldo', show_window),
        pystray.MenuItem('Salir', exit_app)
    )
    
    # Cargar ícono para la bandeja
    try:
        icon_image = load_app_image("METHODO.png")
        
        # Crear el ícono en la bandeja
        AppState.app_icon = pystray.Icon("MethodoRespaldo", icon_image, "Methodo Respaldo", menu)
        
        # Ejecutar el ícono en un hilo separado
        threading.Thread(target=AppState.app_icon.run, daemon=True).start()
        logger.info("Icono de bandeja del sistema iniciado")
    except Exception as e:
        logger.error(f"Error al crear ícono de bandeja: {e}", exc_info=True)
        messagebox.showerror("Error", "No se pudo crear el ícono en la bandeja del sistema.")
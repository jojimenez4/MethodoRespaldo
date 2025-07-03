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
    encrypt, bd_connect_mysql, send_email,
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
            logger.info(f"Inicio de sesión exitoso: usuario {username}")
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
                
                login_window.after(30000, unlock_login)  # 30 segundos

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
    center_window(server_window, 800, 350)

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

    # Campo de contraseña
    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

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
                client, connection_success = bd_connect_mysql(host, port, password)
                
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
                messagebox.showinfo("Información", "Funcionalidad para SQL Server en desarrollo.")
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
    
    # Verificar si hay respaldos programados guardados
    if program_state.get("scheduled", False):
        backup_hours = program_state.get("backup_hours", 4)
        backup_minutes = program_state.get("backup_minutes", 0)
        
        # Configurar estado
        AppState.set_backup_time(backup_hours, backup_minutes)
        AppState.set_scheduled(True)
        AppState.selected_amount = program_state.get("amount", 5)
        
        logger.info(f"Cargada configuración de respaldo: {backup_hours}h:{backup_minutes}m")
    
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
        """Actualiza la etiqueta con la carpeta seleccionada."""
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=folder)
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

    # Estado de programación
    schedule_status = "No programado"
    if AppState.backup_hours is not None and AppState.backup_minutes is not None:
        schedule_status = f"Programado: cada {AppState.backup_hours}h:{AppState.backup_minutes}m"
    
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
            
            # Verificar permisos escribiendo un archivo de prueba
            test_file = os.path.join(folder_path, "test_write.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                if os.path.exists(test_file):
                    os.unlink(test_file)
                logger.info(f"Permisos de escritura verificados en: {folder_path}")
            except Exception as perm_error:
                logger.error(f"Error de permisos de escritura: {perm_error}")
                messagebox.showerror("Error", f"No se tienen permisos de escritura en el directorio: {perm_error}")
                return
        except Exception as dir_error:
            logger.error(f"Error al verificar directorio: {dir_error}")
            messagebox.showerror("Error", f"Error al verificar el directorio: {dir_error}")
            return

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

        # Etiqueta para mostrar el estado actual
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

            if server_data["server_type"] == "MySQL Server (TCP/IP)":
                try:
                    # Actualizar el estado del programa de manera segura usando ConfigManager
                    config_manager.update_program_state(
                        running=True,
                        status="in_progress",
                        backup_dir=folder_path,
                        progress=0
                    )

                    # Lanzar el respaldo en un hilo separado
                    def run_backup() -> None:
                        try:
                            # Crear instancia de BackupManager en lugar de llamar a función
                            backup_manager = BackupManager()
                            result = backup_manager.backup_mysql_database(
                                server_data["password"], 
                                folder_path, 
                                server_data.get("client", "Cliente"), 
                                AppState.selected_amount,
                                server_data,  # Añadir server_data como parámetro
                                update_callback=update_progress
                            )
                            
                            # Actualizar al completar en el hilo principal
                            progress_window.after(0, lambda: completion_tasks(result))
                        except Exception as e:
                            # Manejar errores en el hilo principal
                            progress_window.after(0, lambda: handle_error(e))
                    
                    def completion_tasks(result=True) -> None:
                        if not result:
                            handle_error(Exception("El proceso de respaldo falló."))
                            return
                            
                        update_progress(100, "Respaldo completado.")
                        
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
                        config_manager.update_program_state(
                            status="error",
                            progress=0
                        )
                        
                        if progress_window.winfo_exists():
                            progress_window.destroy()
                        
                        logger.error(f"Error en el respaldo: {e}", exc_info=True)
                        messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
                    
                    # Iniciar el proceso de respaldo en un hilo separado
                    backup_thread = threading.Thread(target=run_backup, daemon=True)
                    backup_thread.start()
                    
                except Exception as e:
                    config_manager.update_program_state(
                        status="error",
                        progress=0
                    )
                    
                    if progress_window.winfo_exists():
                        progress_window.destroy()
                    
                    logger.error(f"Error al iniciar el respaldo: {e}", exc_info=True)
                    messagebox.showerror("Error", f"Error al iniciar el respaldo: {e}")
            else:
                if progress_window.winfo_exists():
                    progress_window.destroy()
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
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
        """Programa un respaldo automático."""
        if backup_hours is None or backup_minutes is None:
            logger.warning("Intento de programar respaldo con horas o minutos nulos")
            return
            
        # Obtener estado actual para asegurar que tenemos valores válidos
        current_folder_path = folder_path
        current_server_data = server_data.copy() if server_data else None
        
        if not current_folder_path or not current_server_data:
            logger.error("No se puede programar respaldo: faltan datos de ruta o servidor")
            return
        
        interval_seconds = (backup_hours * 3600) + (backup_minutes * 60)
        logger.info(f"Programando respaldo cada {interval_seconds} segundos")
        
        # Limpiar programaciones anteriores
        schedule.clear()
        
        # Función de respaldo que captura el estado actual
        def run_backup_task():
            logger.info(f"Ejecutando tarea programada: respaldo cada {backup_hours}h:{backup_minutes}m")
            return execute_programed_backup(current_folder_path, current_server_data)
        
        # Programar nueva tarea
        job = schedule.every(interval_seconds).seconds.do(run_backup_task)
        job.tag("backup_task")
        
        # Actualizar estado
        AppState.set_scheduled(True)
        AppState.set_backup_time(backup_hours, backup_minutes)
        
        logger.info(f"Respaldo programado con éxito: cada {backup_hours}h:{backup_minutes}m")
        
        # Iniciar thread si no está activo
        if AppState.scheduled_backup_thread is None or not AppState.scheduled_backup_thread.is_alive():
            AppState.scheduled_backup_thread = threading.Thread(
                target=run_scheduler, 
                daemon=True
            )
            AppState.scheduled_backup_thread.start()
            logger.info("Thread de respaldos programados iniciado")
    
    def run_scheduler() -> None:
        """Ejecuta el programador de tareas."""
        logger.info("Iniciando programador de respaldos")
        
        try:
            # Verificar que hay tareas programadas
            jobs = list(schedule.jobs)
            if not jobs:
                logger.warning("No hay tareas programadas al iniciar run_scheduler")
                
                # Intentar recuperar configuración y reprogramar
                from config_manager import ConfigManager
                config_manager = ConfigManager()
                program_state = config_manager.get_program_state()
                
                if program_state.get("scheduled", False):
                    backup_hours = program_state.get("backup_hours", 4)
                    backup_minutes = program_state.get("backup_minutes", 0)
                    
                    # Reprogramar con la configuración guardada
                    schedule_backup(backup_hours, backup_minutes)
                    logger.info(f"Reprogramado respaldo con configuración guardada: {backup_hours}h:{backup_minutes}m")
            
            # Bucle principal
            while AppState.running and AppState.scheduled:
                schedule.run_pending()
                
                # Verificar periódicamente si hay tareas
                if not schedule.jobs:
                    logger.warning("No hay tareas programadas durante la ejecución")
                    
                    # Intentar reprogramar con el estado actual
                    if AppState.backup_hours is not None and AppState.backup_minutes is not None:
                        schedule_backup(AppState.backup_hours, AppState.backup_minutes)
                        logger.info(f"Reprogramado respaldo con estado actual: {AppState.backup_hours}h:{AppState.backup_minutes}m")
                
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
                
            if server_data["server_type"] == "MySQL Server (TCP/IP)":
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
                    test_file = os.path.join(folder_path, "test_write.tmp")
                    with open(test_file, 'w') as f:
                        f.write("test")
                    if os.path.exists(test_file):
                        os.remove(test_file)
                    logger.info("Permisos de escritura verificados en directorio de respaldo")
                except Exception as perm_error:
                    logger.error(f"Error de permisos en directorio de respaldo: {perm_error}")
                    send_email(server_data.get("client", "Cliente"), 
                            f"Error de permisos en directorio de respaldo: {perm_error}")
                    return
                    
                # Crear instancia de BackupManager para el respaldo programado
                backup_manager = BackupManager()
                result = backup_manager.backup_mysql_database(
                    server_data["password"], 
                    folder_path, 
                    server_data.get("client", "Cliente"), 
                    AppState.selected_amount,
                    server_data  # Asegurarse de pasar server_data aquí
                )
                
                if result:
                    logger.info("Respaldo programado completado con éxito")
                else:
                    logger.error("Respaldo programado completado con errores")
            else:
                logger.error("Tipo de servidor no soportado para respaldo programado")
                message = "Tipo de servidor no soportado para respaldo programado"
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
        """Muestra el historial de respaldos realizados."""
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
                
            # Buscar archivos de respaldo
            backup_files = [
                entry.path for entry in os.scandir(backup_dir) if entry.is_file() and entry.name.endswith(".7z")
            ]
            
            if not backup_files:
                raise ValueError("No hay respaldos disponibles en el directorio seleccionado.")
                
            # Ordenar por fecha de modificación (más reciente primero)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            
            # Crear lista formateada
            backup_history = [
                f"{os.path.basename(file)} - {datetime.datetime.fromtimestamp(os.path.getmtime(file)).strftime('%Y-%m-%d %H:%M:%S')}"
                for file in backup_files
            ]
            
            # Mostrar en ventana de diálogo
            history_window = customtkinter.CTkToplevel(root)
            active_windows["history_window"] = history_window
            history_window.title("Historial de Respaldos")
            center_window(history_window, 600, 400)
            
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
            
            # Crear scrollable frame para la lista
            scrollable_frame = customtkinter.CTkScrollableFrame(history_frame)
            scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Añadir items a la lista
            for i, history_item in enumerate(backup_history):
                item_frame = customtkinter.CTkFrame(scrollable_frame)
                item_frame.pack(fill="x", pady=2)
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=history_item,
                    anchor="w",
                    font=("Arial", 12)
                )
                item_label.pack(side="left", fill="x", expand=True, padx=5)

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
            
        # Guardar estado actual
        program_state["running"] = False
        program_state["status"] = "stopped"
        save_state(STATUS_PROGRAM, program_state)
        
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def open_advance_options(parent_window: customtkinter.CTk, rounded_label: customtkinter.CTkLabel, schedule_func: Optional[Callable] = None) -> None:
    """Abre la ventana de opciones avanzadas."""
    # Si hay un respaldo programado, confirmar pausa
    if AppState.scheduled:
        pause_message = (
            f"Se pausará el respaldo automático programado "
            f"({str(AppState.backup_hours).zfill(2)}:{str(AppState.backup_minutes).zfill(2)}). "
            f"¿Estás seguro que quieres continuar?"
        )
        if not messagebox.askyesno("Confirmación", pause_message):
            return
        AppState.set_scheduled(False)

    # Crear ventana de configuración
    root = customtkinter.CTk()
    root.title("Configuración Avanzada")
    center_window(root, 500, 500)

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both")

    # Sección de respaldo automático
    autorespaldos_label = customtkinter.CTkLabel(
        frame, 
        text="Respaldo Automático", 
        font=("Arial", 14, "bold")
    )
    autorespaldos_label.pack(pady=5)

    # Marco para tareas programadas
    tasks_frame = customtkinter.CTkFrame(frame)
    tasks_frame.pack(pady=5, padx=10, fill="x", expand=True)

    # Lista para almacenar tareas adicionales
    additional_tasks = []
    
    # Etiqueta para mostrar tareas configuradas
    tasks_label = customtkinter.CTkLabel(
        tasks_frame, 
        text="Tareas configuradas:\n", 
        font=("Arial", 12), 
        anchor="w", 
        justify="left"
    )
    tasks_label.pack(pady=5, padx=5, fill="x")

    def add_task(hour: str = "00", minute: str = "00") -> None:
        """Añade una nueva tarea programada."""
        if len(additional_tasks) >= 3:
            messagebox.showerror("Error", "No se pueden agregar más de 3 tareas en total.")
            return

        # Crear frame para la tarea
        task_frame = customtkinter.CTkFrame(tasks_frame)

        # Selector de hora
        task_hour_label = customtkinter.CTkLabel(task_frame, text="Hora:")
        task_hour_label.pack(side="left", padx=(10, 5), anchor="w")
        task_hour_combobox = customtkinter.CTkComboBox(
            task_frame, 
            values=[str(h).zfill(2) for h in range(24)], 
            width=80, 
            justify="center"
        )
        task_hour_combobox.set(hour)
        task_hour_combobox.pack(side="left", padx=(5, 5), anchor="w")

        # Selector de minuto
        task_minute_label = customtkinter.CTkLabel(task_frame, text="Minuto:")
        task_minute_label.pack(side="left", padx=(5, 5), anchor="w")
        task_minute_combobox = customtkinter.CTkComboBox(
            task_frame, 
            values=[str(m).zfill(2) for m in range(60)], 
            width=80, 
            justify="center"
        )
        task_minute_combobox.set(minute)
        task_minute_combobox.pack(side="left", padx=(5, 5), anchor="w")

        # Botón para eliminar tarea
        remove_button = customtkinter.CTkButton(
            task_frame, 
            text="-", 
            width=30, 
            fg_color="red", 
            command=lambda: remove_task(task_frame)
        )
        remove_button.pack(side="left", padx=(5, 5))

        task_frame.pack(pady=5, padx=10, fill="x")

        # Añadir a la lista de tareas
        additional_tasks.append((task_frame, task_hour_combobox, task_minute_combobox))
        update_tasks_label()

    def remove_task(task_frame: customtkinter.CTkFrame) -> None:
        """Elimina una tarea programada."""
        for task in additional_tasks:
            if task[0] == task_frame:
                additional_tasks.remove(task)
                task_frame.destroy()
                break
        update_tasks_label()

    def update_tasks_label() -> None:
        """Actualiza la etiqueta con las tareas configuradas."""
        tasks_text = "Tareas configuradas:\n"
        AppState.task_configurations.clear()
        
        for idx, (_, hour_combobox, minute_combobox) in enumerate(additional_tasks, start=1):
            hour = hour_combobox.get()
            minute = minute_combobox.get()
            AppState.task_configurations.append((hour, minute))
            tasks_text += f"Tarea {idx}: {hour}:{minute}\n"
            
        tasks_label.configure(text=tasks_text)

    # Botón para añadir tarea
    add_task_button = customtkinter.CTkButton(
        frame, 
        text="+", 
        width=30, 
        fg_color="green", 
        command=add_task
    )
    add_task_button.pack(pady=10, padx=20, anchor="e")

    # Añadir tareas existentes
    for hour, minute in AppState.task_configurations:
        add_task(hour, minute)

    # Control de cantidad máxima de respaldos
    spinbox_var = customtkinter.IntVar(value=AppState.selected_amount)
    spinbox_frame = customtkinter.CTkFrame(frame)
    spinbox_frame.pack(pady=10, side="bottom")

    delete_label = customtkinter.CTkLabel(spinbox_frame, text="Cantidad máx respaldos:")
    delete_label.pack(side="left", padx=5)

    numeric_entry = customtkinter.CTkEntry(
        spinbox_frame, 
        textvariable=spinbox_var, 
        width=50, 
        justify="center"
    )
    numeric_entry.pack(side="left", padx=5)

    def decrease_value() -> None:
        """Disminuye el valor del spinbox."""
        current_value = spinbox_var.get()
        if current_value > 1:
            spinbox_var.set(current_value - 1)
            numeric_entry.delete(0, "end")
            numeric_entry.insert(0, str(spinbox_var.get()))

    decrease_button = customtkinter.CTkButton(
        spinbox_frame, 
        text="-", 
        width=30, 
        command=decrease_value, 
        fg_color="red"
    )
    decrease_button.pack(side="left", padx=5)

    def increase_value() -> None:
        """Aumenta el valor del spinbox."""
        current_value = spinbox_var.get()
        if current_value < 100:
            spinbox_var.set(current_value + 1)
            numeric_entry.delete(0, "end")
            numeric_entry.insert(0, str(spinbox_var.get()))

    increase_button = customtkinter.CTkButton(
        spinbox_frame, 
        text="+", 
        width=30, 
        command=increase_value, 
        fg_color="green"
    )
    increase_button.pack(side="right", padx=0)

    def save_advanced_settings():
        """Guarda la configuración avanzada."""
        try:
            # Procesar tareas configuradas
            AppState.task_configurations.clear()
            for task_frame, task_hour_combobox, task_minute_combobox in additional_tasks:
                try:
                    task_hours = int(task_hour_combobox.get())
                    task_minutes = int(task_minute_combobox.get())
                except ValueError:
                    raise ValueError("Horas o minutos deben ser valores numéricos.")
                    
                if task_hours < 0 or task_hours > 23 or task_minutes < 0 or task_minutes > 59:
                    raise ValueError("Horas o minutos inválidos en una tarea adicional.")
                    
                AppState.task_configurations.append((str(task_hours).zfill(2), str(task_minutes).zfill(2)))

            # Configurar cantidad máxima de respaldos - PERMITIR CUALQUIER VALOR > 0
            selected_amount = spinbox_var.get()
            if selected_amount <= 0:  # Solo validar que sea positivo
                logger.warning(f"Valor de respaldos ({selected_amount}) debe ser mayor que 0. Ajustando.")
                selected_amount = 5  # Valor predeterminado razonable
                spinbox_var.set(5)
                
            AppState.set_amount(selected_amount)
            
            # Verificar directorio de destino
            folder_path = rounded_label.cget("text")
            if not folder_path:
                raise ValueError("No se ha seleccionado ninguna carpeta de destino.")
            
            # Importar ConfigManager y preparar la configuración
            from config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # Guardar toda la configuración de una vez
            update_data = {
                "amount": selected_amount,  # USAR EL VALOR CONFIGURADO SIN AJUSTAR
                "backup_dir": folder_path
            }
            
            # Si hay tareas programadas, incluir la configuración de tiempo
            if AppState.task_configurations:
                hours = int(AppState.task_configurations[0][0])
                minutes = int(AppState.task_configurations[0][1])
                
                # Actualizar estado en memoria
                AppState.set_backup_time(hours, minutes)
                AppState.set_scheduled(True)
                
                # Añadir configuración de tiempo al diccionario de actualización
                update_data["backup_hours"] = hours
                update_data["backup_minutes"] = minutes
                update_data["scheduled"] = True
                
                if schedule_func:
                    schedule_func(hours, minutes)  # Llamar a la función de programación si se proporciona
                    logger.info(f"Respaldo programado cada {hours}h:{minutes}m")
                else:
                    logger.error("No se pudo programar el respaldo: función no disponible")
            else:
                # Si no hay tareas, usar configuración por defecto (4 horas)
                logger.info("No hay tareas configuradas, configurando respaldo predeterminado (4 horas)")
                update_data["backup_hours"] = 4
                update_data["backup_minutes"] = 0
                update_data["scheduled"] = True
                AppState.set_backup_time(4, 0)
                AppState.set_scheduled(True)
            
            # Actualizar todo de una vez
            config_manager.update_program_state(**update_data)
            
            # Verificar que se guardó correctamente
            config_manager.repair_state_file()  # Asegurar que todo se guardó
            
            # Verificar contenido del archivo guardado
            state_after = config_manager.get_program_state()
            logger.info(f"Estado después de guardar: {state_after}")
            
            messagebox.showinfo("Info", "Configuración avanzada guardada correctamente.")
            root.destroy()
            parent_window.deiconify()

        except ValueError as e:
            messagebox.showerror("Error", f"Error en la configuración: {e}")
            root.focus_force()
        except Exception as e:
            logger.error(f"Error al guardar configuración avanzada: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error al guardar configuración: {e}")
            root.destroy()
            parent_window.deiconify()

    # Botón para guardar configuración
    save_button = customtkinter.CTkButton(
        frame, 
        text="Guardar Configuración", 
        command=save_advanced_settings, 
        fg_color="green"
    )
    save_button.pack(side="bottom", pady=15)

    # Manejo del cierre de la ventana
    def on_closing() -> None:
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
        # Guardar estado antes de cerrar
        if program_state:
            program_state["running"] = False
            program_state["status"] = "stopped"
            save_state(STATUS_PROGRAM, program_state)
        
        # Detener programador y threads
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
import customtkinter
import tkinter as tk
from tkinter import filedialog, messagebox
from tkcalendar import DateEntry
import content.functions as f
from tkinter import simpledialog
    
customtkinter.set_appearance_mode("dark") 

def create_login_interface():
    login_window = customtkinter.CTk()
    login_window.title("Login")
    login_window.geometry("400x300")
    
    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)


    #esta wea si cambia la apariencia de oscuro a claro

    switch = customtkinter.StringVar(value="dark")

    def switch_mode():
        if switch.get() == "dark":
            customtkinter.set_appearance_mode("light")
            switch.set("light")
            button.configure(text="claro")  # Cambia el texto a "Modo claro"
        else:
            customtkinter.set_appearance_mode("dark")
            switch.set("dark")
            button.configure(text="oscuro")  # Cambia el texto a "Modo oscuro"




    
    button = customtkinter.CTkSwitch(frame, command=switch_mode, text="oscuro")
    button.pack(pady=10, padx=10, anchor="ne")
        


    # Etiqueta y campo para el nombre de usuario
    username_label = customtkinter.CTkLabel(frame, text="Usuario:", width=20)
    username_label.pack(pady=5)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.insert(0, "admin")  # Usuario por defecto
    username_entry.pack(pady=5)

    # Etiqueta y campo para la contraseña
    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    # Función para verificar el inicio de sesión
    def verify_login():
        username = username_entry.get()
        password = password_entry.get()
        # Aquí puedes agregar la lógica para verificar el usuario y la contraseña
        if username == "admin" and password == "1234":  # Ejemplo de verificación
            messagebox.showinfo("Éxito", "Inicio de sesión exitoso.")
            login_window.destroy()
            create_server_interface()  # Saltar a la interfaz de conexión al servidor
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")

    # Botón de inicio de sesión
    login_button = customtkinter.CTkButton(frame, text="Iniciar sesión", command=verify_login, fg_color="green")
    login_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_login())

    login_window.mainloop()

def create_server_interface():
    server_window = customtkinter.CTk() 
    server_window.title("Conectar al Servidor MySQL")
    server_window.geometry("800x350")

    frame = customtkinter.CTkFrame(server_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Etiqueta y campo para el tipo de servidor
    server_type_label = customtkinter.CTkLabel(frame, text="Tipo de Servidor:", width=30)
    server_type_label.pack(pady=5)
    server_type = customtkinter.CTkComboBox(frame, values=["Seleccionar Base de Datos", "MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"], width=280)
    server_type.set("Seleccionar Base de Datos")
    server_type.pack(pady=5)
    
    # Frame para la dirección IP y el puerto
    ip_port_frame = customtkinter.CTkFrame(frame, fg_color=frame.cget("fg_color"))
    ip_port_frame.pack(pady=5, padx=5, fill="x")

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

    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    # Función para verificar el inicio de sesión
    def verify_server():
        try:
            server_ip = server_ip_entry.get()
            port = int(port_entry.get())
            username = f.user
            password = password_entry.get().encode("utf-8")
            key = f.KEY
            encrypted_password = f.encrypt(key, password)
            server_type_selected = server_type.get()

            # Store server data
            server_data = {
                'server_type': server_type_selected,
                'server_ip': server_ip,
                'port': port,
                'username': username,
                'encrypted_password': encrypted_password
            }

        
            if server_type_selected == "MySQL Server (TCP/IP)":
                if f.bd_server_verify_mysql(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos MySQL Server.")
                    server_window.destroy()
                    open_selection_interface(server_data)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL Server.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    server_window.destroy()
                    open_selection_interface(server_data)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Asigna la función verify_server al botón de inicio de sesión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    server_window.mainloop()
    
def open_selection_interface(server_data=None):
    """Abre la interfaz de selección de documentos."""
    root = customtkinter.CTk()
    root.title("Respaldo local")
    root.geometry("600x400")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=5, padx=5, fill="both", expand=True)

    # Botón para mostrar el historial de respaldos en la esquina superior derecha
    history_button = customtkinter.CTkButton(frame, text="⟳", width=30, command= lambda: show_backup_history(), fg_color="green")
    history_button.pack(pady=10, padx=10, anchor="ne")

    label = customtkinter.CTkLabel(frame, text="Selecciona carpeta destino", font=("Helvetica", 16), width=40)
    label.pack(pady=5, padx=5)

    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=f"Destino: {folder}")
            return folder
        else:
            messagebox.showerror("Error", "No se seleccionó ninguna carpeta.")
            return ""

    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label, fg_color="green")
    folder_button.pack(pady=10)

    result_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12), width=30)
    result_label.pack(pady=10)

    # Frame para la etiqueta redondeada y el icono de calendario
    date_frame = customtkinter.CTkFrame(frame)
    date_frame.pack(pady=10, padx=10, fill="x")

    # Etiqueta redondeada para mostrar la dirección de la carpeta seleccionada
    rounded_label = customtkinter.CTkLabel(date_frame, text="", font=("Arial", 12), corner_radius=10, fg_color="gray", width=40)
    rounded_label.pack(side="left", pady=10, padx=10, fill="x", expand=True)

    # Icono de calendario para seleccionar fecha y hora
    calendar_icon = customtkinter.CTkButton(date_frame, text="📅", width=30, command=lambda: open_calendar(root), fg_color="green")
    calendar_icon.pack(side="right", pady=10, padx=10)

    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: password_compress(rounded_label.cget("text"), server_data), fg_color="green")
    execute_button.pack(pady=10)


# wea pa comprimir con contraseña

    def password_compress(folder_path_label, server_data):
        folder_path = folder_path_label.replace("Destino: ", "")
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return

        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return
            
            server_type_selected = server_data['server_type']
            encrypted_password = server_data['encrypted_password']
            
            # Solicitar contraseña para el archivo comprimido
            rar_password = simpledialog.askstring("Contraseña", "Ingrese una contraseña para el archivo comprimido:", show='*')
            if not rar_password:
                messagebox.showerror("Error", "No se ingresó ninguna contraseña.")
                return

            if server_type_selected == "MySQL Server (TCP/IP)":
                f.backup_mysql_database(encrypted_password, folder_path, rar_password)
                messagebox.showinfo("Éxito", "Respaldo de MySQL completado y comprimido con contraseña.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                f.backup_sql_server_database(encrypted_password, folder_path, rar_password)
                messagebox.showinfo("Éxito", "Respaldo de SQL Server completado y comprimido con contraseña.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")

    

    

    # Función para mostrar el historial de respaldos
    def show_backup_history():
        try:
            # Aquí puedes agregar la lógica para obtener el historial de respaldos
            backup_history = ["Backup 1 - 2023-01-01", "Backup 2 - 2023-02-01", "Backup 3 - 2023-03-01"] # Simulación de historial de respaldos
            if not backup_history:
                raise ValueError("No hay historial de respaldos disponible.")
            messagebox.showinfo("Historial de Respaldos", "\n".join(backup_history))
        except ValueError as ve:
            messagebox.showinfo("Historial de Respaldos", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener el historial de respaldos: {e}")

    # Texto link para abrir la interfaz de configuración avanzada
    advanced_settings_link = customtkinter.CTkLabel(frame, text="Configuración avanzada", text_color="green", font=("Arial", 12), cursor="hand2", width=30)
    advanced_settings_link.pack(pady=10)
    advanced_settings_link.bind("<Button-1>", lambda e: open_backup_interface(root))

    # Función para cambiar el color al hacer hover
    def on_enter(event):
        advanced_settings_link.configure(text_color="deep sky blue")

    def on_leave(event):
        advanced_settings_link.configure(text_color="green")

# Bind the hover events
    advanced_settings_link.bind("<Enter>", on_enter)
    advanced_settings_link.bind("<Leave>", on_leave)


    def on_closing():
        root.destroy()  # Cierra la ventana actual
        create_login_interface()  # Vuelve a abrir la ventana de inicio de sesión

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()

calendar_window = None

def open_calendar(parent_window):
    global calendar_window
    if calendar_window is None or not calendar_window.winfo_exists():
        calendar_window = customtkinter.CTkToplevel(parent_window)
        calendar_window.title("Respaldo automatico") 
        calendar_window.geometry("300x300")
        calendar_window.transient(parent_window)  # Show on top

        calendar = DateEntry(calendar_window, width=12, background='darkblue', foreground='white', borderwidth=2)
        calendar.pack(pady=20)

        # Cuadro de entrada para la hora de inicio
        start_time_label = customtkinter.CTkLabel(calendar_window, text="Hora de inicio:", width=20)
        start_time_label.pack(pady=5)

        start_time_frame = customtkinter.CTkFrame(calendar_window)
        start_time_frame.pack(pady=5)

        start_hour_spinbox = tk.Spinbox(start_time_frame, from_=0, to=23, width=2, format="%02.0f")
        start_hour_spinbox.pack(side="left", padx=(20, 5))
        start_hour_label = customtkinter.CTkLabel(start_time_frame, text="hh", width=5)
        start_hour_label.pack(side="left")

        start_minute_spinbox = tk.Spinbox(start_time_frame, from_=0, to=59, width=2, format="%02.0f")
        start_minute_spinbox.pack(side="left", padx=(20, 5))
        start_minute_label = customtkinter.CTkLabel(start_time_frame, text="mm", width=5)
        start_minute_label.pack(side="left")

        def select_date():
            selected_date = calendar.get_date()
            start_time = f"{start_hour_spinbox.get()}:{start_minute_spinbox.get()}"
            print(f"Fecha seleccionada: {selected_date}")
            print(f"Hora: {start_time}")
            calendar_window.destroy()


        select_button = customtkinter.CTkButton(calendar_window, text="Aplicar", command=select_date, fg_color="green")
        select_button.pack(pady=20)

        calendar_window.protocol("WM_DELETE_WINDOW", lambda: calendar_window.destroy())

def open_backup_interface(parent_window):
    root = customtkinter.CTk()
    root.title("Configuración Avanzada")
    root.geometry("500x600")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    # Primera sección: Opciones de archivo SQL
    sql_file_options_label = customtkinter.CTkLabel(frame, text="Opciones de archivo SQL", font=("Helvetica", 16), anchor="w", width=40)
    sql_file_options_label.pack(pady=10, padx=10, anchor="w")

    # Checkbox para "Estructura"
    structure_var = customtkinter.StringVar()
    structure_checkbox = customtkinter.CTkCheckBox(frame, text="Estructura", variable=structure_var)
    structure_checkbox.pack(pady=5, padx=10, anchor="w")

    # Sub-opciones de SQL (ejemplo)
    drop_table_var = customtkinter.StringVar()
    drop_table_checkbox = customtkinter.CTkCheckBox(frame, text="Agregar declaración DROP TABLE --add-drop-table", variable=drop_table_var)
    drop_table_checkbox.pack(pady=5, padx=30, anchor="w")

    transaction_var = customtkinter.StringVar()
    transaction_checkbox = customtkinter.CTkCheckBox(frame, text="Encerrar exportación en una transacción --single-transaction", variable=transaction_var)
    transaction_checkbox.pack(pady=5, padx=30, anchor="w")

    # Botón de Guardar y Cerrar
    save_button = customtkinter.CTkButton(frame, text="Guardar y Cerrar", command=lambda: close_and_return(root, parent_window), fg_color="green")
    save_button.pack(pady=20, padx=10)

    # Segunda sección: Opciones de Respaldo
    backup_options_label = customtkinter.CTkLabel(frame, text="Opciones de Respaldo", font=("Helvetica", 16), anchor="w", width=40)
    backup_options_label.pack(pady=10, padx=10, anchor="w")

    # Checkbox para "Colocar el respaldo en subcarpeta"
    subfolder_var = customtkinter.StringVar()
    subfolder_checkbox = customtkinter.CTkCheckBox(frame, text="Colocar el respaldo para cada base de datos en su propia subcarpeta", variable=subfolder_var)
    subfolder_checkbox.pack(pady=5, padx=10, anchor="w")

    # Checkbox para estructura y datos
    structure_backup_var = customtkinter.StringVar()
    structure_backup_checkbox = customtkinter.CTkCheckBox(frame, text="Estructura", variable=structure_backup_var)
    structure_backup_checkbox.pack(pady=5, padx=30, anchor="w")

    data_backup_var = customtkinter.StringVar()
    data_backup_checkbox = customtkinter.CTkCheckBox(frame, text="Datos", variable=data_backup_var)
    data_backup_checkbox.pack(pady=5, padx=30, anchor="w")

    # Detectar el cierre de la ventana
    def on_closing():
        root.destroy()  # Cierra la ventana actual
        parent_window.deiconify()  # Rehabilita la ventana padre

    root.protocol("WM_DELETE_WINDOW", on_closing)

    

    # Ocultar la ventana padre mientras la ventana de configuración avanzada está abierta
    parent_window.withdraw()

    root.mainloop()

def close_and_return(current_window, parent_window):
    current_window.destroy()
    parent_window.deiconify()

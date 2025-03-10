from xml.etree.ElementTree import tostring
import customtkinter
from tkinter import filedialog
from tkcalendar import Calendar, DateEntry
# import mysql.connector
from tkinter import messagebox
import content.functions as f

def create_login_interface():
    customtkinter.set_appearance_mode("dark")
    login_window = customtkinter.CTk()
    login_window.title("Login")
    login_window.geometry("400x300")

    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Etiqueta y campo para el nombre de usuario
    username_label = customtkinter.CTkLabel(frame, text="Usuario:")
    username_label.pack(pady=5)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.pack(pady=5)

    # Etiqueta y campo para la contraseña
    password_label = customtkinter.CTkLabel(frame, text="Contraseña:")
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
            create_server_interface()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")

    # Botón de inicio de sesión
    login_button = customtkinter.CTkButton(frame, text="Iniciar sesión", command=verify_login)
    login_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_login())

    login_window.mainloop()

def create_server_interface():
    """Crea la interfaz de inicio de sesión."""
    server_window = customtkinter.CTk() 
    server_window.title("Conectar al Servidor MySQL")
    server_window.geometry("800x500")

    frame = customtkinter.CTkFrame(server_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Etiqueta y campo para el tipo de servidor
    server_type_label = customtkinter.CTkLabel(frame, text="Tipo de Servidor:")
    server_type_label.pack(pady=5)
    server_type = customtkinter.CTkComboBox(frame, values=["MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"])
    server_type.set("MySQL Server (TCP/IP)")  # Valor por defecto
    server_type.pack(pady=5)

    # Etiqueta y campo para el nombre del servidor
    server_name_label = customtkinter.CTkLabel(frame, text="Nombre del Servidor:")
    server_name_label.pack(pady=5)
    server_name_entry = customtkinter.CTkEntry(frame)
    server_name_entry.insert(0, "localhost")  # Valor por defecto
    server_name_entry.pack(pady=5)

    # Etiqueta y campo para el puerto
    port_label = customtkinter.CTkLabel(frame, text="Puerto:")
    port_label.pack(pady=5)
    port_entry = customtkinter.CTkEntry(frame)
    port_entry.insert(0, "3306")  # Puerto por defecto de MySQL
    port_entry.pack(pady=5)

    # Etiqueta y campo para el nombre de usuario
    username_label = customtkinter.CTkLabel(frame, text="Usuario:")
    username_label.pack(pady=5)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.insert(0, "root")  # Usuario por defecto
    username_entry.pack(pady=5)

    # Etiqueta y campo para la contraseña
    password_label = customtkinter.CTkLabel(frame, text="Contraseña:")
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    # Función para verificar el inicio de sesión
    def verify_server():
        try:
            server_ip = server_name_entry.get()
            port = int(port_entry.get())
            username = username_entry.get()
            password = password_entry.get().encode("utf-8")
            key = f.KEY
            encrypted_password = f.encrypt(key, password)
            server_type_selected = server_type.get()

            # Llama a la función correspondiente según el tipo de servidor seleccionado
            if server_type_selected == "MySQL Server (TCP/IP)":
                if f.bd_server_verify_mysql(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos MySQL.")
                    open_selection_interface(server_window)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_server_verify_sql_server(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    open_selection_interface(server_window)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Asigna la función verify_server al botón de inicio de sesión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server)
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    server_window.mainloop()

def open_selection_interface(server_window):
    """Abre la interfaz de selección de documentos."""
    server_window.destroy()  # Cierra la ventana de inicio de sesión

    root = customtkinter.CTk()
    root.title("Respaldo local")
    root.geometry("500x400")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    label = customtkinter.CTkLabel(frame, text="Seleccionar carpeta destino", font=("Helvetica", 16))
    label.pack(pady=12, padx=10)

    # Etiqueta carpeta destino
    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            result_label.configure(text="No se seleccionó carpeta")
            rounded_label.configure(text="")
            return None

    # Botón selección de archivo
    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label)
    folder_button.pack(pady=10)

    # Etiqueta para el resultado
    result_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12))
    result_label.pack(pady=10)

    # Frame para la etiqueta redondeada y el icono de calendario
    date_frame = customtkinter.CTkFrame(frame)
    date_frame.pack(pady=10, padx=10, fill="x")

    # Etiqueta redondeada para mostrar la dirección de la carpeta seleccionada
    rounded_label = customtkinter.CTkLabel(date_frame, text="", font=("Arial", 12), corner_radius=10, fg_color="gray")
    rounded_label.pack(side="left", pady=10, padx=10, fill="x", expand=True)

    # Icono de calendario para seleccionar fecha y hora
    calendar_icon = customtkinter.CTkButton(date_frame, text="📅", width=30, command=lambda: open_calendar(root))
    calendar_icon.pack(side="right", pady=10, padx=10)

    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: print("Ejecutar clicked"))
    execute_button.pack(pady=10)

    # Texto link para abrir la interfaz de configuración avanzada
    advanced_settings_link = customtkinter.CTkLabel(frame, text="Advanced Settings", font=("Arial", 12), text_color="blue", cursor="hand2")
    advanced_settings_link.pack(pady=10)
    advanced_settings_link.bind("<Button-1>", lambda e: open_backup_interface(root))

    # Detectar el cierre de la ventana
    def on_closing():
        root.destroy()  # Cierra la ventana actual
        create_server_interface()  # Vuelve a abrir la ventana de inicio de sesión

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()

calendar_window = None

def open_calendar(parent_window):
    global calendar_window
    if calendar_window is None or not calendar_window.winfo_exists():
        calendar_window = customtkinter.CTkToplevel(parent_window)
        calendar_window.title("Seleccionar Fecha y Hora")
        calendar_window.geometry("300x300")
        calendar_window.transient(parent_window)  # Show on top

        calendar = DateEntry(calendar_window, width=12, background='darkblue', foreground='white', borderwidth=2)
        calendar.pack(pady=20)

        def select_date():
            selected_date = calendar.get_date()
            print(f"Fecha seleccionada: {selected_date}")
            calendar_window.destroy()

        select_button = customtkinter.CTkButton(calendar_window, text="Seleccionar", command=select_date)
        select_button.pack(pady=20)

        calendar_window.protocol("WM_DELETE_WINDOW", lambda: calendar_window.destroy())

def open_backup_interface(parent_window):
    root = customtkinter.CTk()
    root.title("Advanced Settings")
    root.geometry("500x600")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    # Primera sección: Opciones de archivo SQL
    sql_file_options_label = customtkinter.CTkLabel(frame, text="SQL file options", font=("Helvetica", 16), anchor="w")
    sql_file_options_label.pack(pady=10, padx=10, anchor="w")

    # Checkbox para "Structure"
    structure_var = customtkinter.StringVar()
    structure_checkbox = customtkinter.CTkCheckBox(frame, text="Structure", variable=structure_var)
    structure_checkbox.pack(pady=5, padx=10, anchor="w")

    # Sub-opciones de SQL (ejemplo)
    drop_table_var = customtkinter.StringVar()
    drop_table_checkbox = customtkinter.CTkCheckBox(frame, text="Add DROP TABLE statement --add-drop-table", variable=drop_table_var)
    drop_table_checkbox.pack(pady=5, padx=30, anchor="w")

    transaction_var = customtkinter.StringVar()
    transaction_checkbox = customtkinter.CTkCheckBox(frame, text="Enclose export in a transaction --single-transaction", variable=transaction_var)
    transaction_checkbox.pack(pady=5, padx=30, anchor="w")

    # Añadir más opciones de SQL similares aquí...
    # Botón de Guardar y Cerrar
    save_button = customtkinter.CTkButton(frame, text="Save & Close", command=lambda: close_and_return(root, parent_window))
    save_button.pack(pady=20, padx=10)
    
    # Segunda sección: Opciones de Respaldo
    backup_options_label = customtkinter.CTkLabel(frame, text="Backup options", font=("Helvetica", 16), anchor="w")
    backup_options_label.pack(pady=10, padx=10, anchor="w")

    # Checkbox para "Place the backup in subfolder"
    subfolder_var = customtkinter.StringVar()
    subfolder_checkbox = customtkinter.CTkCheckBox(frame, text="Place the backup for each database into its own subfolder", variable=subfolder_var)
    subfolder_checkbox.pack(pady=5, padx=10, anchor="w")

    # Checkbox para estructura y datos
    structure_backup_var = customtkinter.StringVar()
    structure_backup_checkbox = customtkinter.CTkCheckBox(frame, text="Structure", variable=structure_backup_var)
    structure_backup_checkbox.pack(pady=5, padx=30, anchor="w")

    data_backup_var = customtkinter.StringVar()
    data_backup_checkbox = customtkinter.CTkCheckBox(frame, text="Data", variable=data_backup_var)
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












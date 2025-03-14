import customtkinter
import tkinter as tk
from tkinter import filedialog, messagebox
from tkcalendar import DateEntry
import content.functions as f

def create_login_interface():
    customtkinter.set_appearance_mode("dark")
    
    login_window = customtkinter.CTk() 
    login_window.title("Conectar al Servidor MySQL")
    login_window.geometry("800x500")


    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    server_type_label = customtkinter.CTkLabel(frame, text="Tipo de Servidor:")
    server_type_label.pack(pady=5)
    server_type = customtkinter.CTkComboBox(frame, values=["Seleccionar Base de Datos","MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"])
    server_type.set("Seleccionar Base de Datos")
    server_type.pack(pady=5)

    server_ip_label = customtkinter.CTkLabel(frame, text="Dirección IP del Servidor:")
    server_ip_label.pack(pady=5)
    server_ip_entry = customtkinter.CTkEntry(frame)
    server_ip_entry.insert(0, "localhost")
    server_ip_entry.pack(pady=5)

    port_label = customtkinter.CTkLabel(frame, text="Puerto:")
    port_label.pack(pady=5)
    port_entry = customtkinter.CTkEntry(frame)
    port_entry.pack(pady=5)

    username_label = customtkinter.CTkLabel(frame, text="Usuario:")
    username_label.pack(pady=5)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.insert(0, "root")  # Usuario por defecto
    username_entry.pack(pady=5)

    def update_data(event=None):
        server_type_selected = server_type.get()
        username_entry.delete(0, customtkinter.END)
        port_entry.delete(0, customtkinter.END)
        if server_type_selected == "MySQL Server (TCP/IP)":
            username_entry.insert(0, "root")
            port_entry.insert(0, "3306")
        elif server_type_selected == "SQL Server (Windows Authentication)":
            username_entry.insert(0, "sa")
            port_entry.insert(0, "1433")
        else:
            username_entry.insert(0, "")
            port_entry.insert(0, "")

    server_type.bind("<<ComboboxSelected>>", update_data)
    update_data()

    password_label = customtkinter.CTkLabel(frame, text="Contraseña:")
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    def verify_login():
        try:
            server_ip = server_ip_entry.get()
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
                    login_window.destroy()
                    open_selection_interface()  
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    login_window.destroy()
                    open_selection_interface() 
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    login_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_login)
    login_button.pack(pady=20)
    password_entry.bind("<Return>", lambda event: verify_login())

    login_window.mainloop()

def open_selection_interface():
    """Abre la interfaz de selección de documentos."""


    root = customtkinter.CTk()
    root.title("Respaldo local")
    root.geometry("600x400")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=5, padx=5, fill="both", expand=True)

    label = customtkinter.CTkLabel(frame, text="Seleccionar carpeta destino", font=("Helvetica", 16), width=40)
    label.pack(pady=5, padx=5)

    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=f"Destino: {folder}")
            return folder
        else:
            messagebox.showerror("Error", "No se seleccionó ninguna carpeta.")
            return ""

    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label)
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
    calendar_icon = customtkinter.CTkButton(date_frame, text="", width=30, command=lambda: open_calendar(root))
    calendar_icon.pack(side="right", pady=10, padx=10)

    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: print("Ejecutar clicked"))
    execute_button.pack(pady=10)

    # Texto link para abrir la interfaz de configuración avanzada
    advanced_settings_link = customtkinter.CTkLabel(frame, text="Configuración avanzada", font=("Arial", 12), text_color="blue", cursor="hand2", width=30)
    advanced_settings_link.pack(pady=10)
    advanced_settings_link.bind("<Button-1>", lambda e: open_backup_interface(root))

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
        calendar_window.title("Seleccionar Fecha y Hora")
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
            print(f"Hora de inicio: {start_time}")
            calendar_window.destroy()

        select_button = customtkinter.CTkButton(calendar_window, text="Seleccionar", command=select_date)
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
    save_button = customtkinter.CTkButton(frame, text="Guardar y Cerrar", command=lambda: close_and_return(root, parent_window))
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












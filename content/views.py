import os    
import datetime
import time
import threading
import schedule
import customtkinter
from tkinter import filedialog, messagebox, simpledialog, ttk
import content.functions as f

customtkinter.set_appearance_mode("dark") 

def create_login_interface():
    login_window = customtkinter.CTk()
    login_window.title("Login")
    login_window.geometry("400x300")
    
    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    switch = customtkinter.StringVar(value="dark")

    def switch_mode():
        if switch.get() == "dark":
            customtkinter.set_appearance_mode("light")
            button.configure(text="claro")
            switch.set("light")
        else:
            customtkinter.set_appearance_mode("dark")
            button.configure(text="oscuro")
            switch.set("dark")
    
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
                    open_backup_interface(server_data)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL Server.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    server_window.destroy()
                    open_backup_interface(server_data)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "No se ha seleccionado ninguna base de datos.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Asigna la función verify_server al botón de inicio de sesión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    server_window.mainloop()

def open_backup_interface(server_data=None):
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

    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: execute_backup(rounded_label.cget("text"), server_data), fg_color="green")
    execute_button.pack(pady=10)

    scheduled = False

    def execute_backup(folder_path_label, server_data):
        nonlocal scheduled
        folder_path = folder_path_label.replace("Destino: ", "")
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return
        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return
            server_type_selected = server_data['server_type']
            host = server_data['server_ip']
            port = server_data['port']
            user = server_data['username']
            encrypted_password = server_data['encrypted_password']
            if server_type_selected == "MySQL Server (TCP/IP)":
                f.backup_mysql_database(encrypted_password, folder_path)
                client = f.get_database_name(host, port, user, encrypted_password)
                messagebox.showinfo("Éxito", "Respaldo de MySQL completado.")
                message = f"""
                Estimados de {client},
                Junto con saludar, le informamos que el respaldo de datos programado para el dia de hoy, {datetime.datetime.now().strftime('%Y-%m-%d')},
                se ha realizado y completado con exito.

                Saluda atentamente,
                Methodo.
                """
                f.send_email(message)
            elif server_type_selected == "SQL Server (Windows Authentication)":
                f.backup_sql_server_database(encrypted_password, folder_path)
                messagebox.showinfo("Éxito", "Respaldo de SQL Server completado.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
            message = f"Error al ejecutar el respaldo: {e}"
            f.send_email(message)

        if not scheduled:
            scheduled = True
            messagebox.showinfo("Info", "Respaldo automático programado cada 5 minutos.")
            def schedule_backup():
                schedule.every(5).minutes.do(execute_programed_backup, folder_path_label=rounded_label.cget("text"), server_data=server_data)

            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(1)

            schedule_backup()
            threading.Thread(target=run_scheduler, daemon=True).start()

    # def password_compress(folder_path_label, server_data):
    #     folder_path = folder_path_label.replace("Destino: ", "")
    #     if not folder_path:
    #         messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
    #         return

    #     try:
    #         if server_data is None:
    #             messagebox.showerror("Error", "No se recibieron los datos del servidor.")
    #             return
            
    #         server_type_selected = server_data['server_type']
    #         encrypted_password = server_data['encrypted_password']

    #         # Solicitar contraseña para el archivo comprimido
    #         rar_password = simpledialog.askstring("Contraseña", "Ingrese una contraseña para el archivo comprimido:", show='*')
    #         if not rar_password:
    #             messagebox.showerror("Error", "No se ingresó ninguna contraseña.")
    #             return

    #         progress_window = customtkinter.CTkToplevel()
    #         progress_window.title("Progreso")
    #         progress_window.geometry("400x150")

    #         # Centrar la ventana de progreso en la pantalla
    #         parent_x = progress_window.winfo_screenwidth() // 2
    #         parent_y = progress_window.winfo_screenheight() // 2
    #         progress_window.geometry(f"+{parent_x - 200}+{parent_y - 75}")

    #         progress_label = customtkinter.CTkLabel(progress_window, text="Realizando respaldo, por favor espere...")
    #         progress_label.pack(pady=10)

    #         # Barra de progreso
    #         progress_bar = ttk.Progressbar(progress_window, orient="horizontal", mode="indeterminate", length=300)
    #         progress_bar.pack(pady=10)
    #         progress_bar.start()  # Inicia la animación de la barra de progreso
            
    #         progress_window.update()  # Actualiza la ventana para mostrar los cambios


    #         # Realizar el respaldo según el tipo de servidor
    #         if server_type_selected == "MySQL Server (TCP/IP)":
    #             f.backup_mysql_database(encrypted_password, folder_path, rar_password)
    #             messagebox.showinfo("Éxito", "Respaldo de MySQL completado y comprimido con contraseña.")
    #         elif server_type_selected == "SQL Server (Windows Authentication)":
    #             f.backup_sql_server_database(encrypted_password, folder_path, rar_password)
    #             messagebox.showinfo("Éxito", "Respaldo de SQL Server completado y comprimido con contraseña.")
    #         else:
    #             messagebox.showerror("Error", "Tipo de servidor no soportado.")
    #             return
    #     except Exception as e:
    #         messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
    #     finally:
    #         progress_bar.stop()  # Detiene la animación de la barra de progreso
    #         progress_window.destroy()  # Cierra la ventana de progreso
    
    def execute_programed_backup():
        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return
            server_type_selected = server_data['server_type']
            encrypted_password = server_data['encrypted_password']
            folder_path = rounded_label.cget("text").replace("Destino: ", "")
            if server_type_selected == "MySQL Server (TCP/IP)":
                f.backup_mysql_database(encrypted_password, folder_path)
                message = f"Respaldo de MySQL completado. Carpeta: {folder_path}"
                f.send_email(message)
            elif server_type_selected == "SQL Server (Windows Authentication)":
                f.backup_sql_server_database(encrypted_password, folder_path)
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo programado: {e}")
            message = f"Error al ejecutar el respaldo programado: {e}"
            f.send_email(message)

    # Texto link para abrir la interfaz de configuración avanzada
    advanced_settings_link = customtkinter.CTkLabel(frame, text="Configuración avanzada", text_color="green", font=("Arial", 12), cursor="hand2", width=30)
    advanced_settings_link.pack(pady=10)
    advanced_settings_link.bind("<Button-1>", lambda e: open_advance_options(root))

    # Función para cambiar el color al hacer hover
    def on_enter(event):
        advanced_settings_link.configure(text_color="deep sky blue")

    def on_leave(event):
        advanced_settings_link.configure(text_color="green")

    advanced_settings_link.bind("<Enter>", on_enter)
    advanced_settings_link.bind("<Leave>", on_leave) 

    def show_backup_history():
        try:
            # Directorio donde se guardan los respaldos   
            backup_dir = rounded_label.cget("text").replace("Destino: ", "")  # Ruta de respaldos

            # Verifica si el directorio existe
            if not os.path.exists(backup_dir):
                raise ValueError("El directorio de respaldos no existe.")

            # lista de archivos 
            backup_files = [
                os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".rar")
            ]

            # Verifica si hay archivos de respaldo   
            if not backup_files:
                raise ValueError("No hay respaldos disponibles.")

            # Ordena los archivos por fecha de modificación
            backup_files.sort(key=os.path.getmtime, reverse=True)

            # Crea una lista 
            backup_history = [
                f"{os.path.basename(file)} - {datetime.datetime.fromtimestamp(os.path.getmtime(file)).strftime('%Y-%m-%d %H:%M:%S')}"
                for file in backup_files
            ]

            # Mostrar el historial en un cuadro de mensaje
            messagebox.showinfo("Historial de Respaldos", "\n".join(backup_history))
        except ValueError as ve:
            messagebox.showinfo("Historial de Respaldos", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener el historial de respaldos: {e}")

    def on_closing():
        root.destroy()  # Cierra la ventana actual
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def open_advance_options(parent_window):
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
    save_button = customtkinter.CTkButton(frame, text="Guardar y Cerrar", command=lambda: on_closing())
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
    root.mainloop()


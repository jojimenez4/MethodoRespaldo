<<<<<<< HEAD:content/views.py
import customtkinter
import tkinter as tk
from tkinter import filedialog, messagebox
from tkcalendar import DateEntry
import content.functions as f
from tkinter import simpledialog
from tkinter import ttk
import os    
import datetime
import time
=======
import os    
import datetime
import time
import threading
import schedule
import customtkinter
from tkinter import filedialog, messagebox, simpledialog, ttk
from functions import encrypt, bd_connect_mysql, send_email, backup_mysql_database, KEY

>>>>>>> origin/dev:views.py
customtkinter.set_appearance_mode("dark") 

def create_login_interface():
    login_window = customtkinter.CTk()
    login_window.title("Login")
    login_window.geometry("400x300")
    
    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

<<<<<<< HEAD:content/views.py

    

    


    #esta wea si cambia la apariencia de oscuro a claro

    switch = customtkinter.StringVar(value="dark")



=======
    switch = customtkinter.StringVar(value="dark")

>>>>>>> origin/dev:views.py
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
<<<<<<< HEAD:content/views.py
        

    

=======
>>>>>>> origin/dev:views.py

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
            host = server_ip_entry.get()
            port = int(port_entry.get())
            password = password_entry.get().encode("utf-8")
            encrypted_password = encrypt(KEY, password)
            server_type_selected = server_type.get()
            client = ""

        
            if server_type_selected == "MySQL Server (TCP/IP)":
<<<<<<< HEAD:content/views.py
                if f.bd_server_verify_mysql(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos MySQL Server.")
=======
                client, connection_success = bd_connect_mysql(host, port, encrypted_password)
                if connection_success :
                    server_data = [server_type_selected, host, port, encrypted_password, client]
                    messagebox.showinfo("Éxito", f"Conexión exitosa a la base de datos MySQL. Cliente: {client}")
>>>>>>> origin/dev:views.py
                    server_window.destroy()
                    open_backup_interface(server_data)
                else:
<<<<<<< HEAD:content/views.py
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL Server.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    server_window.destroy()
                    open_selection_interface(server_data)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
=======
                    messagebox.showerror("Error", f"Error en la conexión a la base de datos MySQL: {client}")
            # elif server_type_selected == "SQL Server (Windows Authentication)":
            #     if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
            #         messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
            #         server_window.destroy()
            #         open_backup_interface(server_data)
            #     else:
            #         messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
>>>>>>> origin/dev:views.py
            else:
                messagebox.showerror("Error", "No se ha seleccionado ninguna base de datos.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Asigna la función verify_server al botón de inicio de sesión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    server_window.mainloop()
    
# wea pa comprimir con contraseña

<<<<<<< HEAD:content/views.py
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

        progress_window = customtkinter.CTkToplevel()
        progress_window.title("Progreso")
        progress_window.geometry("400x150")

        # Centrar la ventana de progreso en la pantalla
        parent_x = progress_window.winfo_screenwidth() // 2
        parent_y = progress_window.winfo_screenheight() // 2
        progress_window.geometry(f"+{parent_x - 200}+{parent_y - 75}")

        progress_label = customtkinter.CTkLabel(progress_window, text="Realizando respaldo, por favor espere...")
        progress_label.pack(pady=10)

        # Barra de progreso
        progress_bar = ttk.Progressbar(progress_window, orient="horizontal", mode="indeterminate", length=300)
        progress_bar.pack(pady=10)
        progress_bar.start()  # Inicia la animación de la barra de progreso
        
        progress_window.update()  # Actualiza la ventana para mostrar los cambios


        # Realizar el respaldo según el tipo de servidor
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
    finally:
        progress_bar.stop()  # Detiene la animación de la barra de progreso
        progress_window.destroy()  # Cierra la ventana de progreso

def open_selection_interface(server_data=None):
    """Abre la interfaz de selección de documentos."""
=======
def open_backup_interface(server_data=None):
>>>>>>> origin/dev:views.py
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

<<<<<<< HEAD:content/views.py
    # Icono de calendario para seleccionar fecha y hora
    calendar_icon = customtkinter.CTkButton(date_frame, text="📅", width=30, command=lambda: open_calendar(root), fg_color="green")
    calendar_icon.pack(side="right", pady=10, padx=10)

    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: password_compress(rounded_label.cget("text"), server_data), fg_color="green")
    execute_button.pack(pady=10)

     

    # wea pa mostrar el historial de respaldos  
    def show_backup_history():
        try:
            # Directorio donde se guardan los respaldos
            
            backup_dir = "C:\\respaldo"  # Ruta de respaldos

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

            
=======
    # Botón para ejecutar
    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: execute_backup(rounded_label.cget("text"), server_data), fg_color="green")
    execute_button.pack(pady=10)

    scheduled = False

    def execute_backup(folder, server_data):
        nonlocal scheduled
        folder_path = folder.replace("Destino: ", "")
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return
        
        # Crear una ventana de progreso
        progress_window = customtkinter.CTkToplevel(root)
        progress_window.title("Realizando Respaldo")
        progress_window.geometry("300x100")
        progress_window.grab_set()  

        # Barra de progreso
        progressbar = ttk.Progressbar(progress_window, mode='determinate', length=280)
        progressbar.pack(pady=10, padx=10)

        # Etiqueta para mostrar el progreso
        progress_label = customtkinter.CTkLabel(progress_window, text="Iniciando...")
        progress_label.pack(pady=5)

        def update_progress(value, text):
            progressbar['value'] = value
            progress_label.configure(text=text)
            progress_window.update_idletasks()

        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                progress_window.destroy()
                return
            if  server_data[0] == "MySQL Server (TCP/IP)":
                def backup_with_progress():
                    try:
                        backup_mysql_database(server_data[3], folder_path, server_data[4], update_callback=update_progress)
                    except Exception as e:
                        messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
                    finally:
                        progress_window.destroy()

                threading.Thread(target=backup_with_progress, daemon=True).start()
            # elif server_type_selected == "SQL Server (Windows Authentication)":
            #     f.backup_sql_server_database(encrypted_password, folder_path)
            #     messagebox.showinfo("Éxito", "Respaldo de SQL Server completado.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
                progress_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
            progress_window.destroy()

        if not scheduled:
            scheduled = True
            def schedule_backup():
                schedule.every(5).minutes.do(execute_programed_backup, folder_path, server_data=server_data)
                messagebox.showinfo("Info", "Respaldo automático programado cada 5 minutos.")
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(1)
            schedule_backup()
            threading.Thread(target=run_scheduler, daemon=True).start()

    def execute_programed_backup(folder_path, server_data):
        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return
            if  server_data[0] == "MySQL Server (TCP/IP)":
                backup_mysql_database(server_data[3], folder_path, server_data[4])
            # elif server_type_selected == "SQL Server (Windows Authentication)":
            #     f.backup_sql_server_database(encrypted_password, folder_path)
            #     messagebox.showinfo("Éxito", "Respaldo de SQL Server completado.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
            message = f"Error al ejecutar el respaldo: {e}"
            send_email(message)
>>>>>>> origin/dev:views.py

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
            backup_dir = rounded_label.cget("text").replace("Destino: ", "")
            if not os.path.exists(backup_dir):
                raise ValueError("El directorio de respaldos no existe.") 
            backup_files = [
                os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".rar")
            ] 
            if not backup_files:
                raise ValueError("No hay respaldos disponibles.")
            backup_files.sort(key=os.path.getmtime, reverse=True)
            backup_history = [
                f"{os.path.basename(file)} - {datetime.datetime.fromtimestamp(os.path.getmtime(file)).strftime('%Y-%m-%d %H:%M:%S')}"
                for file in backup_files
            ]
            messagebox.showinfo("Historial de Respaldos", "\n".join(backup_history))
        except ValueError as ve:
            messagebox.showinfo("Historial de Respaldos", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener el historial de respaldos: {e}")

<<<<<<< HEAD:content/views.py
    # Función para cambiar el color al hacer hover
    def on_enter(event):
        advanced_settings_link.configure(text_color="deep sky blue")

    def on_leave(event):
        advanced_settings_link.configure(text_color="green")

# hovers de la confi :p

    advanced_settings_link.bind("<Enter>", on_enter)
    advanced_settings_link.bind("<Leave>", on_leave)


    def on_closing():
        root.destroy()  # Cierra la ventana actual
        create_login_interface()  # Vuelve a abrir la ventana de inicio de sesión

=======
    def on_closing():
        root.destroy()  # Cierra la ventana actual
>>>>>>> origin/dev:views.py
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    
    
    
# Función pa programar repaldo 

<<<<<<< HEAD:content/views.py
scheduled_time = None  # Global variable to store the scheduled time

def schedule_backup():
    global scheduled_time
    while True:
        if scheduled_time:
            # Obtener la hora actual
            current_time = datetime.datetime.now().strftime("%H:%M")
            if current_time == scheduled_time:
                try:
                    # Llamar a la función de respaldo automático
                    folder_path = "C:\\respaldo"  # Cambia esto a tu ruta real
                    server_data = {
                        "server_type": "MySQL Server (TCP/IP)",
                        "encrypted_password": f.encrypt(f.KEY, b"Freya-100MTH")  # Cambia esto a tu contraseña
                    }
                    password_compress(f"Destino: {folder_path}", server_data)  # Llamar correctamente
                except Exception as e:
                    print(f"Error al realizar el respaldo automático: {e}")
                finally:
                    # Esperar un minuto para evitar múltiples ejecuciones en el mismo minuto
                    time.sleep(60)
        time.sleep(1)  # Verificar cada segundo

def open_calendar(parent_window):
    global scheduled_time
    time_window = customtkinter.CTkToplevel(parent_window)
    time_window.title("Programar Respaldo Automático")
    time_window.geometry("300x250")
    time_window.transient(parent_window)

    # Etiqueta para la fecha actual
    current_date_label = customtkinter.CTkLabel(time_window, text=f"Fecha actual: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    current_date_label.pack(pady=10)

    # Etiqueta para la hora
    hour_label = customtkinter.CTkLabel(time_window, text="Seleccione hora (HH:MM):")
    hour_label.pack(pady=10)

    # Frame para los cuadros de selección de hora y minutos
    time_frame = customtkinter.CTkFrame(time_window)
    time_frame.pack(pady=10)

    # Spinbox para la hora
    hour_spinbox = tk.Spinbox(time_frame, from_=0, to=23, width=3, format="%02.0f")
    hour_spinbox.pack(side="left", padx=5)

    # Separador entre hora y minutos
    separator_label = customtkinter.CTkLabel(time_frame, text=":")
    separator_label.pack(side="left", padx=5)

    # Spinbox para los minutos
    minute_spinbox = tk.Spinbox(time_frame, from_=0, to=59, width=3, format="%02.0f")
    minute_spinbox.pack(side="left", padx=5)

    # Botón para guardar la hora programada
    def save_time():
        global scheduled_time
        selected_time = f"{hour_spinbox.get()}:{minute_spinbox.get()}"
        try:
            # Validar el formato de la hora
            datetime.datetime.strptime(selected_time, "%H:%M")
            scheduled_time = selected_time
            messagebox.showinfo("Éxito", f"Respaldo programado para hoy a las {scheduled_time}.")
            time_window.destroy()
        except ValueError:
            messagebox.showerror("Error", "Formato de hora inválido. Use HH:MM.")
            

    save_button = customtkinter.CTkButton(time_window, text="Aplicar", command=save_time, fg_color="green")
    save_button.pack(pady=20)
    
    

    #time_window.protocol("WM_DELETE_WINDOW", lambda: time_window.destroy())

def open_backup_interface(parent_window):
=======
def open_advance_options(parent_window):
>>>>>>> origin/dev:views.py
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
<<<<<<< HEAD:content/views.py
    save_button = customtkinter.CTkButton(frame, text="Guardar y Cerrar", command=lambda: close_and_return(root, parent_window), fg_color="green")
=======
    save_button = customtkinter.CTkButton(frame, text="Guardar y Cerrar", command=lambda: on_closing())
>>>>>>> origin/dev:views.py
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
<<<<<<< HEAD:content/views.py

    

    # Ocultar la ventana padre mientras la ventana de configuración avanzada está abierta
    parent_window.withdraw()

=======
>>>>>>> origin/dev:views.py
    root.mainloop()


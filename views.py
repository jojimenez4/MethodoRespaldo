import os    
import datetime
import subprocess
import time
import threading
import schedule
import customtkinter
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image
from functions import encrypt, bd_connect_mysql, send_email, backup_mysql_database, KEY

customtkinter.set_appearance_mode("dark") 

app_running = True

task_configurations = []

backup_hours = None
backup_minutes = None
scheduled = False
scheduled_backup_thread = None

def center_window(window, width, height):
    """Centrar una ventana en la pantalla."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def create_login_interface():
    global app_running
    login_window = customtkinter.CTk()
    login_window.title("Login")
    center_window(login_window, 400, 500)

    switch = customtkinter.StringVar(value="dark")

    def switch_mode():
        if switch.get() == "dark":
            customtkinter.set_appearance_mode("light")
            button.configure(text="claro")
            switch.set("light")
        else:
            def initialize_appearance():
                customtkinter.set_appearance_mode("dark")
            
            initialize_appearance()
            button.configure(text="oscuro")
            switch.set("dark")

    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    button = customtkinter.CTkSwitch(frame, command=switch_mode, text="oscuro")
    button.pack(pady=10, padx=10, anchor="ne")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "assets", "METHODO.png")
    logo_image = Image.open(logo_path)
    logo_ctk_image = CTkImage(light_image=logo_image, dark_image=logo_image, size=(200, 200))
    logo_label = customtkinter.CTkLabel(frame, image=logo_ctk_image, text="")
    logo_label.pack(pady=0)
    
    username_label = customtkinter.CTkLabel(frame, text="Usuario:", width=20)
    username_label.pack(pady=0)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.insert(0, "admin")
    username_entry.pack(pady=0)

    password_label = customtkinter.CTkLabel(frame, text="Contraseña:", width=20)
    password_label.pack(pady=5)
    password_entry = customtkinter.CTkEntry(frame, show="*")
    password_entry.pack(pady=5)

    def verify_login():
        username = username_entry.get()
        password = password_entry.get()
        if username == "admin" and password == "1234":
            messagebox.showinfo("Éxito", "Inicio de sesión exitoso.")
            login_window.destroy()
            create_server_interface()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")

    login_button = customtkinter.CTkButton(frame, text="Iniciar sesión", command=verify_login, fg_color="green")
    login_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_login())

    def on_closing():
        global app_running
        app_running = False
        login_window.destroy()

    login_window.protocol("WM_DELETE_WINDOW", on_closing)
    login_window.mainloop()

def create_server_interface():
    global app_running
    server_window = customtkinter.CTk() 
    server_window.title("Conectar al Servidor MySQL")
    center_window(server_window, 800, 350)

    frame = customtkinter.CTkFrame(server_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    server_type_label = customtkinter.CTkLabel(frame, text="Tipo de Servidor:", width=30)
    server_type_label.pack(pady=5)
    server_type = customtkinter.CTkComboBox(frame, values=["Seleccionar Base de Datos", "MySQL Server (TCP/IP)", "SQL Server (Windows Authentication)"], width=280)
    server_type.set("Seleccionar Base de Datos")
    server_type.pack(pady=5)

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

    def verify_server():
        try:
            host = server_ip_entry.get()
            port = int(port_entry.get())
            password = password_entry.get().encode("utf-8")
            encrypted_password = encrypt(KEY, password)
            server_type_selected = server_type.get()
            client = ""
            if server_type_selected == "MySQL Server (TCP/IP)":
                client, connection_success = bd_connect_mysql(host, port, encrypted_password)
                if connection_success :
                    server_data = [server_type_selected, host, port, encrypted_password, client]
                    messagebox.showinfo("Éxito", f"Conexión exitosa a la base de datos MySQL. Cliente: {client}")
                    server_window.destroy()
                    open_backup_interface(server_data)
                else:
                    messagebox.showerror("Error", f"Error en la conexión a la base de datos MySQL: {client}")
            # elif server_type_selected == "SQL Server (Windows Authentication)":
            #     if f.bd_server_verify_sql_server(server_ip, username, encrypted_password):
            #         messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
            #         server_window.destroy()
            #         open_backup_interface(server_data)
            #     else:
            #         messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "No se ha seleccionado ninguna base de datos.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    server_window.mainloop()
    
def open_file_interface(parent_window):
    parent_window.withdraw()
    file_window = customtkinter.CTk()
    file_window.title("Desencriptar")
    center_window(file_window, 400, 300)

    frame = customtkinter.CTkFrame(file_window)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    label = customtkinter.CTkLabel(frame, text="Selecciona el archivo a desencriptar", font=("Helvetica", 16), width=40)
    label.pack(pady=5, padx=5)

    file_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12), width=40,corner_radius=10, fg_color="gray")
    file_label.pack(fill="x", expand=True)

    def select_file():
        file_path = filedialog.askopenfilename(filetypes=[("RAR Files", "*.rar")])
        if file_path:
            file_label.configure(text=f"Archivo: {file_path}")
        else:
            file_label.configure(text="Archivo no seleccionado")
    
    browse_button = customtkinter.CTkButton(frame, text=" Buscar Archivo", command=select_file, fg_color="green")
    browse_button.pack(pady=10)

    def insert_file():
        file_path = file_label.cget("text").replace("Archivo: ", "")
        if not file_path or file_path == "Archivo no seleccionado":
            messagebox.showerror("Error", "No se seleccionó ningún archivo.")
            return

        password = simpledialog.askstring("Contraseña", "Ingrese una contraseña para el archivo:", show="*")
        if password:
            messagebox.showinfo("Éxito", f"Archivo '{file_path}' protegido con contraseña.")
        else:
            messagebox.showerror("Error", "No se ingresó ninguna contraseña.")

    insert_button = customtkinter.CTkButton(frame, text="Desencriptar", command=insert_file, fg_color="blue")
    insert_button.pack(pady=10)

    def on_closing():
        parent_window.deiconify()
        file_window.destroy()

    file_window.protocol("WM_DELETE_WINDOW", on_closing)
    file_window.mainloop()

def open_backup_interface(server_data=None):
    global app_running, backup_hours, backup_minutes
    root = customtkinter.CTk()
    root.title("Respaldo local")
    center_window(root, 600, 400)

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=5, padx=5, fill="both", expand=True)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "assets", "METHODO.png")
    logo_image = Image.open(logo_path)
    logo_ctk_image = customtkinter.CTkImage(light_image=logo_image, dark_image=logo_image, size=(200, 200))

    top_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
    top_frame.pack(pady=10, padx=10, fill="x")

    logo_label = customtkinter.CTkLabel(top_frame, image=logo_ctk_image, text="")
    logo_label.pack(side="left", padx=50)

    buttons_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
    buttons_frame.pack(side="right", padx=10)

    history_button = customtkinter.CTkButton(buttons_frame, text="⟳ Historial", width=30, command=lambda: show_backup_history(), fg_color="green")
    history_button.pack(pady=5, anchor="e")

    eye_button = customtkinter.CTkButton(buttons_frame, text="👁 Desencriptar", width=30, command=lambda: open_file_interface(root), fg_color="RoyalBlue1")
    eye_button.pack(pady=5, anchor="e")

    advanced_settings_button = customtkinter.CTkButton(buttons_frame, text="⚙ Configuración avanzada", command=lambda: open_advance_options(root, rounded_label, server_data), fg_color="DarkOrange3", width=150)
    advanced_settings_button.pack(pady=5, anchor="e")

    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=folder)
            return folder
        else:
            messagebox.showerror("Error", "No se seleccionó ninguna carpeta.")
            return ""

    lupa_path = os.path.join(base_dir, "assets", "lupa.png")
    lupa_image = Image.open(lupa_path)
    lupa_ctk_image = customtkinter.CTkImage(light_image=lupa_image, dark_image=lupa_image, size=(30, 30))

    lupa_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
    lupa_frame.pack(pady=10, padx=10, fill="x")

    lupa_button = customtkinter.CTkButton(lupa_frame, image=lupa_ctk_image, text="", command=update_label, fg_color="green", width=120, height=32)
    lupa_button.pack(side="left", padx=5)

    rounded_label = customtkinter.CTkLabel(lupa_frame, text="", font=("Arial", 12), corner_radius=10, fg_color="gray", width=30)
    rounded_label.pack(side="left", padx=5, fill="x", expand=True)

    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: execute_backup(rounded_label.cget("text"), server_data, backup_hours, backup_minutes), fg_color="green")
    execute_button.pack(pady=10)

    folder_path = ""
    def execute_backup(folder, server_data, backup_hours, backup_minutes):
        global scheduled
        nonlocal folder_path
        folder_path = folder.replace("Destino: ", "")
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return

        progress_window = None

        def update_progress(value, text):
            if progress_window and progress_window.winfo_exists():
                progressbar['value'] = value
                progress_label.configure(text=text)
                progress_window.update_idletasks()

        progress_window = customtkinter.CTkToplevel(root)
        progress_window.title("Realizando Respaldo")
        progress_window.geometry("300x100")
        center_window(progress_window, 300, 100)

        progressbar = ttk.Progressbar(progress_window, mode='determinate', length=280)
        progressbar.pack(pady=10, padx=10)

        progress_label = customtkinter.CTkLabel(progress_window, text="Iniciando...")
        progress_label.pack(pady=5)

        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return

            if server_data[0] == "MySQL Server (TCP/IP)":
                def backup_with_progress():
                    try:
                        backup_mysql_database(server_data[3], folder_path, server_data[4], update_callback=update_progress)
                        update_progress(100, "Respaldo completado.")
                        messagebox.showinfo("Éxito", "Respaldo completado con éxito.")
                        if backup_hours or backup_minutes:
                            schedule_backup(backup_hours, backup_minutes)
                            ocultar_ventana()
                            threading.Thread(target=run_scheduler, daemon=True).start()
                            messagebox.showinfo("Info", f"Respaldo automático programado cada {backup_hours} horas y {backup_minutes} minutos.")
                        else:
                            messagebox.showinfo("Info", "Respaldo automático no programado.")
                    except subprocess.CalledProcessError as e:
                        messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
                    except Exception as e:
                            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
                    finally:
                            progress_window.destroy()
                threading.Thread(target=backup_with_progress, daemon=True).start()
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")         

    def schedule_backup(backup_hours, backup_minutes):
        interval_seconds = (backup_hours * 3600) + (backup_minutes * 60)
        schedule.every(interval_seconds).seconds.do(lambda: execute_programed_backup(folder_path, server_data))
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    def execute_programed_backup(folder_path, server_data):
        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                return
            if server_data[0] == "MySQL Server (TCP/IP)":
                backup_mysql_database(server_data[3], folder_path, server_data[4])
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
            message = f"Error al ejecutar el respaldo: {e}"
            send_email(message)

    def ocultar_ventana():
        root.withdraw()
    
    def show_backup_history():
        try:
            backup_dir = rounded_label.cget("text").replace("Destino: ", "")
            if not os.path.exists(backup_dir):
                raise ValueError("El directorio de respaldos no existe.")
            backup_files = [
                entry.path for entry in os.scandir(backup_dir) if entry.is_file() and entry.name.endswith(".rar")
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

    def on_closing():
        global app_running
        app_running = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def open_advance_options(parent_window, rounded_label, server_data=None):
    global scheduled, scheduled_backup_thread, task_configurations, backup_hours, backup_minutes

    if scheduled:
        pause_message = f"Se pausará el respaldo automático de la tarea en {str(backup_hours).zfill(2)}:{str(backup_minutes).zfill(2)}. ¿Estás seguro que quieres continuar?"
        if not messagebox.askyesno("Confirmación", pause_message):
            return
        scheduled = False

    parent_window.withdraw()
    root = customtkinter.CTk()
    root.title("Configuración Avanzada")
    center_window(root, 500, 500)

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both")

    autorespaldos_label = customtkinter.CTkLabel(frame, text="Auto respaldos", font=("Arial", 14, "bold"))
    autorespaldos_label.pack(pady=5)

    tasks_frame = customtkinter.CTkFrame(frame)
    tasks_frame.pack(pady=5, padx=10, fill="x", expand=True)

    additional_tasks = []

    def add_task(hour="00", minute="00"):
        if len(additional_tasks) >= 3:
            messagebox.showerror("Error", "No se pueden agregar más de 3 tareas en total.")

        task_frame = customtkinter.CTkFrame(tasks_frame)

        task_hour_label = customtkinter.CTkLabel(task_frame, text="Hora:")
        task_hour_label.pack(side="left", padx=(10, 5), anchor="w")
        task_hour_combobox = customtkinter.CTkComboBox(task_frame, values=[str(h).zfill(2) for h in range(24)], width=80, justify="center")
        task_hour_combobox.set(hour)
        task_hour_combobox.pack(side="left", padx=(5, 5), anchor="w")

        task_minute_label = customtkinter.CTkLabel(task_frame, text="Minuto:")
        task_minute_label.pack(side="left", padx=(5, 5), anchor="w")
        task_minute_combobox = customtkinter.CTkComboBox(task_frame, values=[str(m).zfill(2) for m in range(60)], width=80, justify="center")
        task_minute_combobox.set(minute)
        task_minute_combobox.pack(side="left", padx=(5, 5), anchor="w")

        task_hour_combobox.configure(justify="center")
        task_minute_combobox.configure(justify="center")

        remove_button = customtkinter.CTkButton(task_frame, text="-", width=30, fg_color="red", command=lambda: remove_task(task_frame))
        remove_button.pack(side="left", padx=(5, 5))

        task_frame.pack(pady=5, padx=10, fill="x")

        additional_tasks.append((task_frame, task_hour_combobox, task_minute_combobox))
        update_tasks_label()

    def remove_task(task_frame):
        for task in additional_tasks:
            if task[0] == task_frame:
                additional_tasks.remove(task)
                task_frame.destroy()
                break
        update_tasks_label()

    def update_tasks_label():
        tasks_text = "Tareas configuradas:\n"
        task_configurations.clear()
        for idx, (_, hour_combobox, minute_combobox) in enumerate(additional_tasks, start=1):
            hour = hour_combobox.get()
            minute = minute_combobox.get()
            task_configurations.append((hour, minute))
            tasks_text += f"Tarea {idx}: {hour}:{minute}\n"
        tasks_label.configure(text=tasks_text)

    tasks_label = customtkinter.CTkLabel(tasks_frame, text="Tareas configuradas:\n", font=("Arial", 12), anchor="w", justify="left")
    tasks_label.pack(pady=5, padx=5, fill="x")

    add_task_button = customtkinter.CTkButton(frame, text="+", width=30, fg_color="green", command=add_task)
    add_task_button.pack(pady=20, padx=20, anchor="e")

    for hour, minute in task_configurations:
        add_task(hour, minute)

    spinbox_var = customtkinter.IntVar(value=1)
    spinbox_frame = customtkinter.CTkFrame(frame)
    spinbox_frame.pack(pady=10, side="bottom")

    delete_label = customtkinter.CTkLabel(spinbox_frame, text="Borrar respaldos:")
    delete_label.pack(side="left", padx=5)

    numeric_entry = customtkinter.CTkEntry(spinbox_frame, textvariable=spinbox_var, width=50, justify="center")
    numeric_entry.pack(side="left", padx=5)

    def decrease_value():
        current_value = spinbox_var.get()
        if current_value > 1:
            spinbox_var.set(current_value - 1)
            numeric_entry.delete(0, "end")
            numeric_entry.insert(0, str(spinbox_var.get()))

    decrease_button = customtkinter.CTkButton(spinbox_frame, text="-", width=30, command=decrease_value, fg_color="red")
    decrease_button.pack(side="left", padx=5)

    def increase_value():
        current_value = spinbox_var.get()
        if current_value < 100:
            spinbox_var.set(current_value + 1)
            numeric_entry.delete(0, "end")
            numeric_entry.insert(0, str(spinbox_var.get()))

    increase_button = customtkinter.CTkButton(spinbox_frame, text="+", width=30, command=increase_value, fg_color="green")
    increase_button.pack(side="right", padx=0)

    def save_advanced_settings():
        global scheduled, scheduled_backup_thread, app_running, task_configurations, backup_hours, backup_minutes
        try:
            task_configurations.clear()
            for task_frame, task_hour_combobox, task_minute_combobox in additional_tasks:
                task_hours = int(task_hour_combobox.get())
                task_minutes = int(task_minute_combobox.get())
                if task_hours < 0 or task_hours > 23 or task_minutes < 0 or task_minutes > 59:
                    raise ValueError("Horas o minutos inválidos en una tarea adicional.")
                task_configurations.append((str(task_hours).zfill(2), str(task_minutes).zfill(2)))

            if task_configurations:
                backup_hours = int(task_configurations[0][0])
                backup_minutes = int(task_configurations[0][1])
                scheduled = True

            selected_value = spinbox_var.get()
            if selected_value > 0:
                messagebox.showinfo("Cantidad seleccionada", f"Cantidad de respaldos a borrar: {selected_value}")
            else:
                raise ValueError("El valor de respaldos a borrar debe ser mayor que 0.")

            folder_path = rounded_label.cget("text").replace("Destino: ", "")
            if not folder_path:
                raise ValueError("No se ha seleccionado ninguna carpeta de destino.")
            parent_window.update_idletasks()
            rounded_label.configure(text=f"Destino: {folder_path}")

            messagebox.showinfo("Configuración Guardada", "Configuración avanzada guardada correctamente.")
            root.destroy()
            parent_window.deiconify()

        except ValueError as e:
            messagebox.showerror("Error", f"Error en la configuración: {e}")
            root.destroy()
            parent_window.deiconify()
        except Exception as e:
            print(f"An error occurred in save_advanced_settings: {e}")

    save_button = customtkinter.CTkButton(frame, text="Guardar Configuración", command=save_advanced_settings, fg_color="green")
    save_button.pack(side="bottom", pady=5)

    def on_closing():
        global app_running
        app_running = False
        root.destroy()
        parent_window.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
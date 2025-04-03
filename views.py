import os    
import datetime
import time
import threading
import schedule
import customtkinter
from tkinter import filedialog, messagebox, simpledialog, ttk, Spinbox
from functions import encrypt, bd_connect_mysql, send_email, backup_mysql_database, KEY
from PIL import Image, ImageTk  # Import PIL for image handling
from customtkinter import CTkImage  # Import CTkImage for handling images

customtkinter.set_appearance_mode("dark") 

# Add a global flag to track if the app is running
app_running = True

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
    center_window(login_window, 400, 500)  # Centrar la ventana

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

    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Move the switch button to the top-right corner
    button = customtkinter.CTkSwitch(frame, command=switch_mode, text="oscuro")
    button.pack(pady=10, padx=10, anchor="ne")  # Positioned at the top-right corner


    #logo methodo
    base_dir = os.path.dirname(os.path.abspath(__file__))  # Get the current directory
    logo_path = os.path.join(base_dir, "assets", "METHODO.png")
    logo_image = Image.open(logo_path)
    logo_ctk_image = CTkImage(light_image=logo_image, dark_image=logo_image, size=(200, 200))  # Use CTkImage
    logo_label = customtkinter.CTkLabel(frame, image=logo_ctk_image, text="")
    logo_label.pack(pady=0)  # Positioned below the switch button
    

    # Etiqueta y campo para el nombre de usuario
    username_label = customtkinter.CTkLabel(frame, text="Usuario:", width=20)
    username_label.pack(pady=0)
    username_entry = customtkinter.CTkEntry(frame)
    username_entry.insert(0, "admin")  # Usuario por defecto
    username_entry.pack(pady=0)

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

    def on_closing():
        global app_running
        app_running = False
        login_window.destroy()  # Cierra la ventana actual

    login_window.protocol("WM_DELETE_WINDOW", on_closing)
    login_window.mainloop()

def create_server_interface():
    global app_running
    server_window = customtkinter.CTk() 
    server_window.title("Conectar al Servidor MySQL")
    center_window(server_window, 800, 350)  # Centrar la ventana

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

    # Asigna la función verify_server al botón de inicio de sesión
    server_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_server, fg_color="green")
    server_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_server())

    def on_closing():
        global app_running
        app_running = False
        server_window.destroy()  # Cierra la ventana actual

    server_window.protocol("WM_DELETE_WINDOW", on_closing)
    server_window.mainloop()
    
# wea pa comprimir con contraseña

def open_file_interface(parent_window):
    parent_window.withdraw()  # Hide the parent window
    file_window = customtkinter.CTk()
    file_window.title("Desencritar")
    center_window(file_window, 400, 300)  # Centrar la ventana

    frame = customtkinter.CTkFrame(file_window)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    #texto para label
    label = customtkinter.CTkLabel(frame, text="Selecciona el archivo a desencriptar", font=("Helvetica", 16), width=40)
    label.pack(pady=5, padx=5)

    # Label to display the selected file path
    file_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12), width=40,corner_radius=10, fg_color="gray")
    file_label.pack(fill="x", expand=True)

    # Function to select a file
    # Función para seleccionar un archivo
    def select_file():
        file_path = filedialog.askopenfilename(filetypes=[("RAR Files", "*.rar")])
        if file_path:
            file_label.configure(text=f"Archivo: {file_path}")  # Actualizar el texto del label
        else:
            file_label.configure(text="Archivo no seleccionado")  # Mostrar mensaje si no se selecciona archivo
    
    # Button to browse for a file
    browse_button = customtkinter.CTkButton(frame, text="Buscar Archivo", command=select_file, fg_color="green")
    browse_button.pack(pady=10)

    # Function to insert the file with a password
    def insert_file():
        file_path = file_label.cget("text").replace("Archivo: ", "")
        if not file_path or file_path == "Archivo no seleccionado":
            messagebox.showerror("Error", "No se seleccionó ningún archivo.")
            return

        # Prompt for a password
        password = simpledialog.askstring("Contraseña", "Ingrese una contraseña para el archivo:", show="*")
        if password:
            messagebox.showinfo("Éxito", f"Archivo '{file_path}' protegido con contraseña.")
        else:
            messagebox.showerror("Error", "No se ingresó ninguna contraseña.")

    # Button to insert the file
    insert_button = customtkinter.CTkButton(frame, text="Desencriptar", command=insert_file, fg_color="blue")
    insert_button.pack(pady=10)

 

    def on_closing():
        parent_window.deiconify()  # Restore the parent window
        file_window.destroy()

    file_window.protocol("WM_DELETE_WINDOW", on_closing)
    file_window.mainloop()

def open_backup_interface(server_data=None):
    global app_running
    root = customtkinter.CTk()
    root.title("Respaldo local")
    center_window(root, 600, 400)

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=5, padx=5, fill="both", expand=True)

    history_button = customtkinter.CTkButton(frame, text="⟳", width=30, command=lambda: show_backup_history(), fg_color="green")
    history_button.pack(pady=10, padx=10, anchor="ne")

    eye_button = customtkinter.CTkButton(frame, text="👁", width=30, command=lambda: open_file_interface(root), fg_color="blue")
    eye_button.pack(pady=10, padx=10, anchor="ne")

    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            rounded_label.configure(text=folder)
            return folder
        else:
            messagebox.showerror("Error", "No se seleccionó ninguna carpeta.")
            return ""

    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label, fg_color="green")
    folder_button.pack(pady=5)

    result_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12), width=30)
    result_label.pack(pady=0)

    date_frame = customtkinter.CTkFrame(frame)
    date_frame.pack(pady=5, padx=5, fill="x", expand=True)

    rounded_label = customtkinter.CTkLabel(date_frame, text="", font=("Arial", 12), corner_radius=10, fg_color="gray", width=40)
    rounded_label.pack(pady=5, fill="x", expand=True)

    execute_button = customtkinter.CTkButton(frame, text="Ejecutar", command=lambda: execute_backup(rounded_label.cget("text"), server_data), fg_color="green")
    execute_button.pack(pady=10)

    scheduled = None

    def execute_backup(folder, server_data):
        global app_running
        nonlocal scheduled
        folder_path = folder.replace("Destino: ", "")
        if not folder_path:
            messagebox.showerror("Error", "No se ha seleccionado una carpeta de destino.")
            return

        progress_window = customtkinter.CTkToplevel(root)
        progress_window.title("Realizando Respaldo")
        progress_window.geometry("300x100")
        progress_window.overrideredirect(True)

        progress_window.update_idletasks()
        screen_width = progress_window.winfo_screenwidth()
        screen_height = progress_window.winfo_screenheight()
        window_width = 300
        window_height = 100
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        progress_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        progress_window.grab_set()

        progressbar = ttk.Progressbar(progress_window, mode='determinate', length=280)
        progressbar.pack(pady=10, padx=10)

        progress_label = customtkinter.CTkLabel(progress_window, text="Iniciando...")
        progress_label.pack(pady=5)

        def update_progress(value, text):
            if app_running and progress_window.winfo_exists():
                progressbar['value'] = value
                progress_label.configure(text=text)
                progress_window.update_idletasks()

        try:
            if server_data is None:
                messagebox.showerror("Error", "No se recibieron los datos del servidor.")
                progress_window.destroy()
                return
            if server_data[0] == "MySQL Server (TCP/IP)":
                def backup_with_progress():
                    try:
                        backup_mysql_database(server_data[3], folder_path, server_data[4], update_callback=update_progress)
                        update_progress(100, "Respaldo completado.")
                    except Exception as e:
                        if progress_window.winfo_exists():
                            messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
                    finally:
                        if progress_window.winfo_exists():
                            progress_window.destroy()

                threading.Thread(target=backup_with_progress, daemon=True).start()
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
                progress_window.destroy()
        except Exception as e:
            if progress_window.winfo_exists():
                messagebox.showerror("Error", f"Error al ejecutar el respaldo: {e}")
            progress_window.destroy()

        def schedule_backup():
            global backup_hours, backup_minutes
            if backup_hours is None or backup_minutes is None:
                messagebox.showerror("Error", "No se ha configurado el tiempo de respaldo automático.")
                return

            interval_seconds = (backup_hours * 3600) + (backup_minutes * 60)
            schedule.every(interval_seconds).seconds.do(execute_programed_backup, folder_path, server_data=server_data)

            messagebox.showinfo("Info", f"Respaldo automático programado cada {backup_hours} horas y {backup_minutes} minutos.")

            def run_schedule():
                while app_running:
                    schedule.run_pending()
                    time.sleep(1)

            threading.Thread(target=run_schedule, daemon=True).start()

        if not scheduled:
            scheduled = True
            threading.Thread(target=schedule_backup, daemon=True).start()

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

    advanced_settings_link = customtkinter.CTkLabel(frame, text="Configuración avanzada", text_color="green", font=("Arial", 12), cursor="hand2", width=30)
    advanced_settings_link.pack(pady=10)
    advanced_settings_link.bind("<Button-1>", lambda e: open_advance_options(root, rounded_label, server_data))

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

    def on_closing():
        global app_running
        app_running = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

# Función pa programar repaldo 

scheduled_backup_thread = None
scheduled = False  # Variable para saber si el respaldo está programado


def open_advance_options(parent_window, rounded_label, server_data=None):  # Add server_data as a parameter
    global scheduled, scheduled_backup_thread  # aki se llaman las variables globales
    parent_window.withdraw()  # Hide the parent window
    root = customtkinter.CTk()
    root.title("Configuración Avanzada")
    center_window(root, 500, 600)  # Centrar la ventana

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    # Lista para almacenar las tareas adicionales
    additional_tasks = []


    def add_task():
        if len(additional_tasks) >= 2:  # Máximo 2 tareas adicionales
            messagebox.showerror("Error", "No se pueden agregar más de 3 tareas en total.")
            return

        # Crear un nuevo frame para la tarea adicional
        task_frame = customtkinter.CTkFrame(frame)

        # Campo para horas
        task_hour_label = customtkinter.CTkLabel(task_frame, text="Hora:")
        task_hour_label.pack(side="left", padx=(10, 5), anchor="w")  # Adjusted padding and anchor
        task_hour_combobox = customtkinter.CTkComboBox(task_frame, values=[str(h).zfill(2) for h in range(24)], width=80, justify="center")
        task_hour_combobox.set("00")
        task_hour_combobox.pack(side="left", padx=(5, 5), anchor="w")  # Adjusted padding and anchor

        # Campo para minutos
        task_minute_label = customtkinter.CTkLabel(task_frame, text="Minuto:")
        task_minute_label.pack(side="left", padx=(5, 5), anchor="w")
        task_minute_combobox = customtkinter.CTkComboBox(task_frame, values=[str(m).zfill(2) for m in range(60)], width=80, justify="center")
        task_minute_combobox.set("00")
        task_minute_combobox.pack(side="left", padx=(5, 5), anchor="w")

        # Botón para eliminar la tarea
        remove_button = customtkinter.CTkButton(task_frame, text="-", width=30, fg_color="red", command=lambda: remove_task(task_frame))
        remove_button.pack(side="left", padx=(5, 5))

        # Insertar la tarea en el frame
        task_frame.pack(pady=5, padx=10, fill="x")

        # Mover el Spinbox y el botón de guardar hacia abajo
        spinbox_frame.pack_forget()
        save_button.pack_forget()
        spinbox_frame.pack(pady=10, after=task_frame)
        save_button.pack(pady=20)

        # Agregar la tarea a la lista
        additional_tasks.append((task_frame, task_hour_combobox, task_minute_combobox))

    def remove_task(task_frame):
        for task in additional_tasks:
            if task[0] == task_frame:
                additional_tasks.remove(task)
                task_frame.destroy()
                break

        # Reajustar la posición del Spinbox y el botón de guardar
        spinbox_frame.pack_forget()
        save_button.pack_forget()
        spinbox_frame.pack(pady=10)
        save_button.pack(pady=20)

    # Botón para agregar tareas adicionales
    add_task_button = customtkinter.CTkButton(frame, text="+", width=30, fg_color="green", command=add_task)
    add_task_button.pack(pady=10, padx=5, anchor="ne")

    # Frame para las entradas de horas y minutos
    time_frame = customtkinter.CTkFrame(frame)
    time_frame.pack(pady=0, padx=5, fill="x", anchor="center")  # Ajustar padx para alineación

    # Campo para horas
    hour_label = customtkinter.CTkLabel(time_frame, text="Hora:")
    hour_label.pack(side="left", padx=(15, 5))  # Añadir padding para alineación
    hour_combobox = customtkinter.CTkComboBox(time_frame, values=[str(h).zfill(2) for h in range(24)], width=80)
    hour_combobox.set("00")  # Valor predeterminado
    hour_combobox.pack(side="left", padx=(5, 5))  # Ajustar padding

    # Campo para minutos
    minute_label = customtkinter.CTkLabel(time_frame, text="Minuto:")
    minute_label.pack(side="left", padx=(5, 5))  # Añadir padding para alineación
    minute_combobox = customtkinter.CTkComboBox(time_frame, values=[str(m).zfill(2) for m in range(60)], width=80)
    minute_combobox.set("00")  # Valor predeterminado
    minute_combobox.pack(side="left", padx=(5, 5))  # Ajustar padding

        # Centrar el texto dentro del combobox
    hour_combobox.configure(justify="center")
    minute_combobox.configure(justify="center")

    spinbox_var = customtkinter.IntVar(value=1)

    # Frame para el Spinbox
    spinbox_frame = customtkinter.CTkFrame(frame)
    spinbox_frame.pack(pady=10)

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
        global scheduled, scheduled_backup_thread, app_running  # Access global variables
        try:
            # Verificar si se seleccionó una carpeta de destino
            folder_path = rounded_label.cget("text").replace("Destino: ", "")
            if not folder_path:
                raise ValueError("No se ha seleccionado ninguna carpeta de destino.")

            # Check if a backup process is running
            if scheduled:
                confirm = messagebox.askyesno(
                    "Confirmación",
                    "Un respaldo automático está en curso. ¿Deseas detenerlo para configurar uno nuevo?"
                )
                if confirm:
                    # Stop the current backup process
                    app_running = False  # Signal threads to stop
                    if scheduled_backup_thread is not None and scheduled_backup_thread.is_alive():
                        scheduled_backup_thread.join(timeout=5)  # Wait for the thread to finish
                    schedule.clear()  # Clear all scheduled tasks
                    scheduled = False  # Mark as not scheduled
                    app_running = True  # Reset the flag for new processes

            # Save the default task configuration
            hours = int(hour_combobox.get())
            minutes = int(minute_combobox.get())
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                raise ValueError("Horas o minutos inválidos.")
            global backup_hours, backup_minutes
            backup_hours = hours
            backup_minutes = minutes

            # Save additional tasks
            for task_frame, task_hour_combobox, task_minute_combobox in additional_tasks:
                task_hours = int(task_hour_combobox.get())
                task_minutes = int(task_minute_combobox.get())
                if task_hours < 0 or task_hours > 23 or task_minutes < 0 or task_minutes > 59:
                    raise ValueError("Horas o minutos inválidos en una tarea adicional.")
                # Save additional tasks as needed (e.g., to a list or file)

            # Show message for selected spinbox value
            selected_value = spinbox_var.get()
            if selected_value > 0:  # Ensure a valid value is selected
                messagebox.showinfo("Cantidad seleccionada", f"Cantidad de respaldos a borrar: {selected_value}")

            # Update the destination path in the main interface
            parent_window.update_idletasks()  # Ensure changes are reflected
            rounded_label.configure(text=f"Destino: {folder_path}")

            messagebox.showinfo("Configuración Guardada", "Configuración avanzada guardada correctamente.")
            root.destroy()  # Close the current window
            parent_window.deiconify()  # Re-enable the main window

        except ValueError as e:
            messagebox.showerror("Error", f"Error en la configuración: {e}")
            root.destroy()  # Close the current window in case of error
            parent_window.deiconify()  # Re-enable the parent window

    save_button = customtkinter.CTkButton(frame, text="Guardar Configuración", command=save_advanced_settings, fg_color="green")
    save_button.pack(pady=20)

    # Detectar el cierre de la ventana
    def on_closing():
        global app_running
        app_running = False
        root.destroy()  # Cierra la ventana actual
        parent_window.deiconify()  # Rehabilita la ventana padre


    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
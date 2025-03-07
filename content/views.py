from xml.etree.ElementTree import tostring
import customtkinter
from tkinter import filedialog
# import mysql.connector
from tkinter import messagebox
import content.functions as f

def create_login_interface():
    customtkinter.set_appearance_mode("dark")
    
    """Crea la interfaz de inicio de sesión."""
    login_window = customtkinter.CTk() 
    login_window.title("Conectar al Servidor MySQL")
    login_window.geometry("800x500")

    frame = customtkinter.CTkFrame(login_window, corner_radius=10)
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
    def verify_login():
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
                if f.bd_login_verify_mysql(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos MySQL.")
                    open_selection_interface(login_window)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos MySQL.")
            elif server_type_selected == "SQL Server (Windows Authentication)":
                if f.bd_login_verify_sql_server(server_ip, port, username, encrypted_password):
                    messagebox.showinfo("Éxito", "Conexión exitosa a la base de datos SQL Server.")
                    open_selection_interface(login_window)
                else:
                    messagebox.showerror("Error", "Error en la conexión a la base de datos SQL Server.")
            else:
                messagebox.showerror("Error", "Tipo de servidor no soportado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar a la base de datos: {e}")

    # Asigna la función verify_login al botón de inicio de sesión
    login_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_login)
    login_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_login())

    login_window.mainloop()

def open_selection_interface(login_window):
    """Abre la interfaz de selección de documentos."""
    login_window.destroy()  # Cierra la ventana de inicio de sesión

    root = customtkinter.CTk()
    root.title("Respaldo local")
    root.geometry("500x300")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    label = customtkinter.CTkLabel(frame, text="Seleccionar carpeta destino", font=("Helvetica", 16))
    label.pack(pady=12, padx=10)

    # Etiqueta carpeta destino
    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            result_label.config(text=f"Destino seleccionado: {folder}")
            return folder
        else:
            result_label.config(text="No se seleccionó carpeta")
            return None

    # Botón selección de archivo
    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label)
    folder_button.pack(pady=10)

    # Etiqueta para el resultado
    result_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12))
    result_label.pack(pady=10)

    # Detectar el cierre de la ventana
    def on_closing():
        root.destroy()  # Cierra la ventana actual
        create_login_interface()  # Vuelve a abrir la ventana de inicio de sesión

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Evitar que se abran múltiples ventanas
    root.grab_set()
    root.mainloop()












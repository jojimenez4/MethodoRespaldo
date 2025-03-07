import customtkinter
from tkinter import filedialog, messagebox
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

    login_button = customtkinter.CTkButton(frame, text="Conectar", command=verify_login)
    login_button.pack(pady=20)

    password_entry.bind("<Return>", lambda event: verify_login())

    login_window.mainloop()

def open_selection_interface(login_window):
    login_window.destroy()

    root = customtkinter.CTk()
    root.title("Respaldo local")
    root.geometry("500x300")

    frame = customtkinter.CTkFrame(root)
    frame.pack(pady=20, padx=60, fill="both", expand=True)

    label = customtkinter.CTkLabel(frame, text="Seleccionar carpeta destino", font=("Helvetica", 16))
    label.pack(pady=12, padx=10)

    def update_label():
        folder = filedialog.askdirectory()
        if folder:
            result_label.config(text=f"Destino seleccionado: {folder}")
            return folder
        else:
            result_label.config(text="No se seleccionó carpeta")
            return None

    folder_button = customtkinter.CTkButton(frame, text="Seleccionar Carpeta", command=update_label)
    folder_button.pack(pady=10)

    result_label = customtkinter.CTkLabel(frame, text="", font=("Arial", 12))
    result_label.pack(pady=10)

    def on_closing():
        root.destroy()
        create_login_interface()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.grab_set()
    root.mainloop()












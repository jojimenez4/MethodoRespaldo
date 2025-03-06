import customtkinter 
from tkinter import filedialog
#import mysql.connector
from tkinter import messagebox

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
    server_type = customtkinter.CTkComboBox(frame, values=["MySQL Server (TCP/IP)"])
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

    # Contenedor para los botones
    button_frame = customtkinter.CTkFrame(frame)
    button_frame.pack(pady=20)


    # Botón para iniciar sesión
    login_button = customtkinter.CTkButton(button_frame, text="Conectar", command=lambda: open_selection_interface(login_window))
    login_button.pack(side="left", padx=10)

    cancel_button = customtkinter.CTkButton(button_frame, text="Cancelar", command=lambda: open_selection_interface(login_window))
    cancel_button.pack(side="left", padx=10)

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

    # Etiqueta y campo para el archivo de origen
    source_label = customtkinter.CTkLabel(frame, text="Archivo de Origen:")
    source_label.pack(pady=5)
    source_entry = customtkinter.CTkEntry(frame, width=300)
    source_entry.pack(side="left", pady=5, padx=5)
    source_button = customtkinter.CTkButton(frame, text="Browse", command=lambda: browse_file(source_entry))
    source_button.pack(side="left", pady=5, padx=5)

    # Etiqueta y campo para el archivo de destino
    dest_label = customtkinter.CTkLabel(frame, text="Archivo de Destino:")
    dest_label.pack(pady=5)
    dest_entry = customtkinter.CTkEntry(frame, width=300)
    dest_entry.pack(side="left", pady=5, padx=5)
    dest_button = customtkinter.CTkButton(frame, text="Browse", command=lambda: browse_file(dest_entry))
    dest_button.pack(side="left", pady=5, padx=5)

    root.mainloop()

def browse_file(entry):
    """Abre un cuadro de diálogo para seleccionar un archivo y muestra la ruta en el campo de entrada."""
    file_path = filedialog.askopenfilename()
    if file_path:
        entry.delete(0, customtkinter.END)
        entry.insert(0, file_path)   



# Llama a la función para crear la interfaz de inicio de sesión
create_login_interface()









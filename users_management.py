"""
Módulo para gestionar usuarios desde la interfaz gráfica.
Proporciona funciones para añadir, editar y eliminar usuarios.
"""

import os
import customtkinter
import logging
from tkinter import messagebox
from typing import Dict, Any, Callable, Optional

from auth_manager import AuthManager

# Configuración de logging
logger = logging.getLogger("BackupSystem.UsersManagement")

class UserManagementWindow:
    """Ventana para gestionar usuarios."""
    
    def __init__(self, parent, close_callback: Optional[Callable] = None):
        """
        Inicializa la ventana de gestión de usuarios.
        
        Args:
            parent: Ventana padre
            close_callback: Función a llamar al cerrar
        """
        self.parent = parent
        self.close_callback = close_callback
        self.auth_manager = AuthManager()
        self.create_window()
    
    def center_window(self, window, width, height):
        """Centra una ventana en la pantalla."""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_window(self):
        """Crea la ventana de gestión de usuarios."""
        self.window = customtkinter.CTkToplevel(self.parent)
        self.window.title("Gestión de Usuarios")
        self.center_window(self.window, 600, 500)
        self.window.grab_set()  # Modal
        
        # Marco principal
        frame = customtkinter.CTkFrame(self.window)
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Título
        title_label = customtkinter.CTkLabel(
            frame, 
            text="Gestión de Usuarios", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)
        
        # Panel de botones (arriba)
        buttons_frame = customtkinter.CTkFrame(frame)
        buttons_frame.pack(pady=5, fill="x")
        
        add_button = customtkinter.CTkButton(
            buttons_frame, 
            text="Añadir Usuario", 
            command=self.add_user_dialog,
            fg_color="green"
        )
        add_button.pack(side="left", padx=5, pady=5)
        
        refresh_button = customtkinter.CTkButton(
            buttons_frame, 
            text="Actualizar Lista", 
            command=self.refresh_users_list
        )
        refresh_button.pack(side="left", padx=5, pady=5)
        
        # Panel de usuarios (lista)
        users_frame = customtkinter.CTkFrame(frame)
        users_frame.pack(pady=5, padx=5, fill="both", expand=True)
        
        # Crear scrollable frame para la lista de usuarios
        self.users_list_frame = customtkinter.CTkScrollableFrame(users_frame)
        self.users_list_frame.pack(fill="both", expand=True)
        
        # Cargar usuarios
        self.refresh_users_list()
        
        # Panel de botones (abajo)
        bottom_buttons_frame = customtkinter.CTkFrame(frame)
        bottom_buttons_frame.pack(pady=5, fill="x")
        
        close_button = customtkinter.CTkButton(
            bottom_buttons_frame, 
            text="Cerrar", 
            command=self.close_window,
            fg_color="gray"
        )
        close_button.pack(side="right", padx=5, pady=5)
        
        # Manejo del cierre
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
    
    def close_window(self):
        """Cierra la ventana."""
        if self.close_callback:
            self.close_callback()
        self.window.destroy()
    
    def refresh_users_list(self):
        """Actualiza la lista de usuarios."""
        # Limpiar lista actual
        for widget in self.users_list_frame.winfo_children():
            widget.destroy()
        
        # Obtener usuarios
        users = self.auth_manager.get_users()
        
        if not users:
            no_users_label = customtkinter.CTkLabel(
                self.users_list_frame,
                text="No hay usuarios registrados",
                font=("Arial", 12, "italic")
            )
            no_users_label.pack(pady=10)
            return
        
        # Añadir cabecera
        header_frame = customtkinter.CTkFrame(self.users_list_frame)
        header_frame.pack(fill="x", pady=5)
        
        username_header = customtkinter.CTkLabel(
            header_frame,
            text="Nombre de Usuario",
            font=("Arial", 12, "bold")
        )
        username_header.pack(side="left", expand=True, fill="x", padx=5)
        
        actions_header = customtkinter.CTkLabel(
            header_frame,
            text="Acciones",
            font=("Arial", 12, "bold")
        )
        actions_header.pack(side="right", padx=5)
        
        # Añadir usuarios
        for i, username in enumerate(sorted(users)):
            self.create_user_entry(username, i % 2 == 0)
    
    def create_user_entry(self, username: str, alternate_color: bool = False):
        """
        Crea una entrada para un usuario en la lista.
        
        Args:
            username: Nombre de usuario
            alternate_color: Si se debe usar color alternativo
        """
        bg_color = "#2b2b2b" if alternate_color else "#222222"
        
        user_frame = customtkinter.CTkFrame(self.users_list_frame)
        user_frame.pack(fill="x", pady=2)
        
        username_label = customtkinter.CTkLabel(
            user_frame,
            text=username,
            anchor="w"
        )
        username_label.pack(side="left", expand=True, fill="x", padx=10)
        
        # Botones de acción
        actions_frame = customtkinter.CTkFrame(user_frame, fg_color="transparent")
        actions_frame.pack(side="right", padx=5)
        
        change_pwd_button = customtkinter.CTkButton(
            actions_frame,
            text="Cambiar Contraseña",
            command=lambda u=username: self.change_password_dialog(u),
            width=100,
            height=25,
            fg_color="blue"
        )
        change_pwd_button.pack(side="left", padx=2)
        
        delete_button = customtkinter.CTkButton(
            actions_frame,
            text="Eliminar",
            command=lambda u=username: self.delete_user_confirm(u),
            width=70,
            height=25,
            fg_color="red"
        )
        delete_button.pack(side="left", padx=2)
    
    def add_user_dialog(self):
        """Muestra un diálogo para añadir un usuario."""
        dialog = customtkinter.CTkToplevel(self.window)
        dialog.title("Añadir Usuario")
        dialog.geometry("400x300")
        dialog.grab_set()  # Modal
        
        frame = customtkinter.CTkFrame(dialog)
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        title_label = customtkinter.CTkLabel(
            frame, 
            text="Añadir Nuevo Usuario", 
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=10)
        
        # Campo de usuario
        username_label = customtkinter.CTkLabel(frame, text="Nombre de Usuario:")
        username_label.pack(pady=5)
        username_entry = customtkinter.CTkEntry(frame, width=200)
        username_entry.pack(pady=5)
        
        # Campo de contraseña
        password_label = customtkinter.CTkLabel(frame, text="Contraseña:")
        password_label.pack(pady=5)
        password_entry = customtkinter.CTkEntry(frame, show="*", width=200)
        password_entry.pack(pady=5)
        
        # Campo de confirmar contraseña
        confirm_label = customtkinter.CTkLabel(frame, text="Confirmar Contraseña:")
        confirm_label.pack(pady=5)
        confirm_entry = customtkinter.CTkEntry(frame, show="*", width=200)
        confirm_entry.pack(pady=5)
        
        # Mensaje de error
        error_label = customtkinter.CTkLabel(frame, text="", text_color="red")
        error_label.pack(pady=5)
        
        # Función para añadir usuario
        def add_user():
            username = username_entry.get().strip()
            password = password_entry.get()
            confirm = confirm_entry.get()
            
            # Validaciones
            if not username:
                error_label.configure(text="El nombre de usuario no puede estar vacío")
                return
            
            if not password or len(password) < 6:
                error_label.configure(text="La contraseña debe tener al menos 6 caracteres")
                return
            
            if password != confirm:
                error_label.configure(text="Las contraseñas no coinciden")
                return
            
            # Añadir usuario
            if self.auth_manager.add_user(username, password, role="admin"):
                messagebox.showinfo("Éxito", f"Usuario {username} añadido correctamente")
                dialog.destroy()
                self.refresh_users_list()
            else:
                error_label.configure(text=f"No se pudo añadir el usuario {username}")
        
        # Botones
        buttons_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
        buttons_frame.pack(pady=10)
        
        add_button = customtkinter.CTkButton(
            buttons_frame,
            text="Añadir",
            command=add_user,
            fg_color="green",
            width=100
        )
        add_button.pack(side="left", padx=5)
        
        cancel_button = customtkinter.CTkButton(
            buttons_frame,
            text="Cancelar",
            command=dialog.destroy,
            fg_color="gray",
            width=100
        )
        cancel_button.pack(side="left", padx=5)
    
    def change_password_dialog(self, username: str):
        """
        Muestra un diálogo para cambiar la contraseña de un usuario.
        
        Args:
            username: Nombre de usuario
        """
        dialog = customtkinter.CTkToplevel(self.window)
        dialog.title(f"Cambiar Contraseña: {username}")
        dialog.geometry("400x250")
        dialog.grab_set()  # Modal
        
        frame = customtkinter.CTkFrame(dialog)
        frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        title_label = customtkinter.CTkLabel(
            frame, 
            text=f"Cambiar Contraseña: {username}", 
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=10)
        
        # Campo de nueva contraseña
        password_label = customtkinter.CTkLabel(frame, text="Nueva Contraseña:")
        password_label.pack(pady=5)
        password_entry = customtkinter.CTkEntry(frame, show="*", width=200)
        password_entry.pack(pady=5)
        
        # Campo de confirmar contraseña
        confirm_label = customtkinter.CTkLabel(frame, text="Confirmar Contraseña:")
        confirm_label.pack(pady=5)
        confirm_entry = customtkinter.CTkEntry(frame, show="*", width=200)
        confirm_entry.pack(pady=5)
        
        # Mensaje de error
        error_label = customtkinter.CTkLabel(frame, text="", text_color="red")
        error_label.pack(pady=5)
        
        # Función para cambiar contraseña
        def change_password():
            password = password_entry.get()
            confirm = confirm_entry.get()
            
            # Validaciones
            if not password or len(password) < 6:
                error_label.configure(text="La contraseña debe tener al menos 6 caracteres")
                return
            
            if password != confirm:
                error_label.configure(text="Las contraseñas no coinciden")
                return
            
            # Cambiar contraseña
            if self.auth_manager.change_password(username, password):
                messagebox.showinfo("Éxito", f"Contraseña de {username} cambiada correctamente")
                dialog.destroy()
            else:
                error_label.configure(text=f"No se pudo cambiar la contraseña de {username}")
        
        # Botones
        buttons_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
        buttons_frame.pack(pady=10)
        
        change_button = customtkinter.CTkButton(
            buttons_frame,
            text="Cambiar",
            command=change_password,
            fg_color="blue",
            width=100
        )
        change_button.pack(side="left", padx=5)
        
        cancel_button = customtkinter.CTkButton(
            buttons_frame,
            text="Cancelar",
            command=dialog.destroy,
            fg_color="gray",
            width=100
        )
        cancel_button.pack(side="left", padx=5)
    
    def delete_user_confirm(self, username: str):
        """
        Muestra confirmación para eliminar un usuario.
        
        Args:
            username: Nombre de usuario a eliminar
        """
        # Verificar que no sea el último usuario
        if len(self.auth_manager.get_users()) <= 1:
            messagebox.showerror(
                "Error", 
                "No se puede eliminar el último usuario del sistema."
            )
            return
        
        # Pedir confirmación
        confirm = messagebox.askyesno(
            "Confirmar eliminación", 
            f"¿Está seguro de que desea eliminar el usuario {username}?\n\nEsta acción no se puede deshacer.",
            icon="warning"
        )
        
        if confirm:
            if self.auth_manager.delete_user(username):
                messagebox.showinfo("Éxito", f"Usuario {username} eliminado correctamente")
                self.refresh_users_list()
            else:
                messagebox.showerror("Error", f"No se pudo eliminar el usuario {username}")
    
    def reset_password(self, username: str):
        """
        Restablece la contraseña de un usuario.
        
        Args:
            username: Nombre de usuario
        """
        confirm = messagebox.askyesno(
            "Confirmar restablecimiento", 
            f"¿Está seguro de que desea restablecer la contraseña de {username}?\n\nSe generará una contraseña aleatoria.",
            icon="question"
        )
        
        if confirm:
            new_password = self.auth_manager.reset_password(username)
            if new_password:
                messagebox.showinfo(
                    "Contraseña restablecida", 
                    f"La nueva contraseña para {username} es:\n\n{new_password}\n\nGuárdela en un lugar seguro."
                )
            else:
                messagebox.showerror("Error", f"No se pudo restablecer la contraseña de {username}")
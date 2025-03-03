import customtkinter

customtkinter.set_appearance_mode("dark")

root = customtkinter.CTk()
root.title("Custom Button Example")
root.geometry("600x400")

frame = customtkinter.CTkFrame(root)
frame.pack(pady=20, padx=60, fill="both", expand=True)

label = customtkinter.CTkLabel(frame, text="Custom Button Example", font=("Helvetica", 16))
label.pack(pady=12, padx=10)
# Create a custom button with a custom background color


root.mainloop()

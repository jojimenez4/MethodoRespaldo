from content.views import open_selection_interface
from content.functions import encrypt, decrypt

if __name__ == "__main__":
    try:
        print("Attempting to create login interface...")
        open_selection_interface()
        print("login interface created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

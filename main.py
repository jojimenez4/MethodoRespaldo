from content.views import create_login_interface
from content.functions import encrypt, decrypt

if __name__ == "__main__":
    try:
        print("Attempting to create login interface...")
        create_login_interface()
        print("login interface created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

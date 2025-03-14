from content.views import create_login_interface

if __name__ == "__main__":
    try:
        print("Attempting to create login interface...")
        create_login_interface()
        print("Login interface created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

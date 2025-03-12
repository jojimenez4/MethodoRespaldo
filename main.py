from content.views import create_login_interface

if __name__ == "__main__":
    try:
        create_login_interface()
    except Exception as e:
        print(f"An error occurred: {e}")

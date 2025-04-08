from views import create_login_interface

if __name__ == "__main__":
    try:
        create_login_interface()
    except Exception as e:
        raise e
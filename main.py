import threading
from content.views import create_login_interface, schedule_backup

if __name__ == "__main__":
    try:
        backup_thread = threading.Thread(target=schedule_backup, daemon=True)
        backup_thread.start()
        create_login_interface()
    except Exception as e:
        print(f"An error occurred: {e}")

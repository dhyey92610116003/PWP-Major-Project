import sys
from PySide6.QtWidgets import QApplication
from ui.dashboard import Dashboard
from ui.login import LoginScreen
from machine.machine_controller import MachineController
from config.settings import SettingsManager

def main():
    app = QApplication(sys.argv)
    
    # Load configuration
    settings = SettingsManager()
    
    # Initialize Core Controllers
    machine_controller = MachineController()
    
    # Show Login Screen first
    login = LoginScreen(settings)
    if login.exec() == LoginScreen.Accepted:
        # User authenticated successfully
        
        # Initialize UI
        window = Dashboard(machine_controller, settings)
        window.show()
        
        # Connect signals and start hardware threads
        machine_controller.start()
        
        sys.exit(app.exec())
    else:
        # User cancelled or closed the login window
        sys.exit(0)

if __name__ == "__main__":
    main()

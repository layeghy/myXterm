import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.mainwindow import MainWindow
import traceback
from utils import resource_path

def main():
    try:
        # Create QApplication FIRST - required before any QObjects
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon(resource_path('build/resources/icon.ico')))
        # Initialize settings manager (QObject requires QApplication to exist)
        from ui.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        
        # Load appropriate stylesheet based on settings
        theme = settings_manager.get("appearance", "theme")
        if theme == "light":
            stylesheet_path = resource_path("ui/style_light.qss")
        else:
            stylesheet_path = resource_path("ui/style.qss")
        
        with open(stylesheet_path, "r") as f:
            app.setStyleSheet(f.read())
            
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_msg = traceback.format_exc()
        print("ERROR:", error_msg)
        with open("app.log", "w") as f:
            f.write(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()

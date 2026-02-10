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
        app.setWindowIcon(QIcon(resource_path('resources', 'icon.ico')))
        
        # Initialize settings manager (QObject requires QApplication to exist)
        from ui.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        
        # Load appropriate stylesheet based on settings
        theme = settings_manager.get("appearance", "theme")
        if theme == "light":
            stylesheet_path = resource_path("ui", "style_light.qss")
        else:
            stylesheet_path = resource_path("ui", "style.qss")
        
        # Performance: Read and cache stylesheet
        try:
            with open(stylesheet_path, "r", encoding='utf-8') as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Could not load stylesheet: {e}")
            
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_msg = traceback.format_exc()
        print("ERROR:", error_msg)
        try:
            with open("app.log", "w") as f:
                f.write(error_msg)
        except:
            pass  # If we can't write the log, at least we tried
        sys.exit(1)


if __name__ == "__main__":
    main()

# myXterm

myXterm is a lightweight, modern terminal emulator for Windows built with Python and PyQt6. It supports SSH connections and local shell sessions with a focused, tabbed interface similar to MobaXterm.

## 🚀 Features

- **Multi-tab Interface**: Manage multiple SSH or local sessions in a single window.
- **SSH Support**: Full SSH client support with password encryption.
- **Local Terminal**: High-performance local terminal using `winpty` for proper PTY emulation.
- **Secure Storage**: Encrypted storage for session credentials.
- **Theming**: Support for dark and light modes with custom QSS styling.
- **Scrollback Buffer**: Integrated history buffer with support for terminal-clearing commands.
- **Terminal Emulation**: Robust ANSI/VT100 support via `pyte`.

## 🏗️ Project Architecture

The project follows a modular architecture separating the UI from the connection logic:

### Frontend (UI) - `ui/`
- **`MainWindow`**: The main application container and tab management.
- **`Terminal`**: Core terminal widget using `QPlainTextEdit` and `pyte`.
- **`SessionManager`**: Handles session definitions and the session list.
- **`SettingsManager`**: Manages user preferences and application state.
- **Stylesheets**: Custom `.qss` files for consistent, modern aesthetics.

### Backend - `ssh/`
- **`SSHBackend`**: Manages SSH connections using `Paramiko`.
- **`LocalSession`**: Manages local Windows shell sessions using `winpty`.

### Security & Utils
- **`security.py`**: Handles AES encryption for sensitive data like session passwords.
- **`utils.py`**: Helper functions for resource paths and environment detection.

## 📁 Folder Structure

```text
myXterm/
├── ssh/                # Backend session logic
│   ├── backend.py      # SSH implementation (Paramiko)
│   └── local_session.py # Local shell implementation (winpty)
├── ui/                 # PyQt6 UI components
│   ├── mainwindow.py   # Main UI shell
│   ├── terminal.py     # Terminal emulator widget
│   └── style.qss       # Modern dark theme
├── main.py             # Entry point
├── security.py         # Encryption logic
├── build_installer.py  # Automation for building the installer
└── myXterm.spec        # PyInstaller configuration
```

## 🛠️ Getting Started

### Prerequisites

- Python 3.8+
- [pywinpty](https://github.com/spyder-ide/pywinpty) (required for local terminal support on Windows)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/layeghy/myXterm.git
   cd myXterm
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## 📦 Building from Source

To create a standalone executable and an installer:

1. Ensure you have PyInstaller and NSIS (if creating the installer) installed.
2. Run the build script:
   ```bash
   python build_installer.py
   ```
3. The output will be located in the `dist/` directory.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

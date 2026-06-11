"""
OpenFOAM Manager 3D — Punto de entrada.
Simula rompimiento de presas con fluidos no newtonianos en 3D.
Canal: L × H × W configurable (ejemplo: 1.6 × 0.6 × 0.15 m)
"""
import sys


def main() -> int:
    missing = []
    for pkg in ["PyQt5", "matplotlib", "numpy"]:
        try: __import__(pkg)
        except ImportError: missing.append(pkg)
    if missing:
        print("ERROR: Faltan dependencias:")
        for p in missing: print(f"  - {p}")
        print("\nInstale con: pip install -r requirements.txt")
        return 1

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("OpenFOAM Manager 3D")
    app.setApplicationVersion("1.0.0")
    app.setFont(QFont("Arial", 9))
    app.setStyleSheet("""
        QMainWindow { background:#F5F7FA; }
        QTabWidget::pane { border:1px solid #E0E0E0; background:white; border-radius:4px; }
        QTabBar::tab { background:#EAEEF2; border:1px solid #D0D5DD;
            padding:6px 14px; border-bottom:none; border-radius:4px 4px 0 0; font-size:11px; }
        QTabBar::tab:selected { background:white; color:#2C5F8A;
            font-weight:bold; border-bottom:2px solid #2C5F8A; }
        QTabBar::tab:hover:!selected { background:#DDE3EB; }
        QGroupBox { font-weight:bold; border:1px solid #D0D5DD; border-radius:6px;
            margin-top:8px; padding-top:4px; background:white; }
        QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left;
            padding:0 6px; color:#2C5F8A; font-size:11px; }
        QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {
            border:1px solid #CBD5E1; border-radius:4px;
            padding:3px 6px; background:white; }
        QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus, QComboBox:focus {
            border:1px solid #2C5F8A; }
        QPushButton { border:1px solid #CBD5E1; border-radius:4px;
            padding:4px 12px; background:#F0F4F8; }
        QPushButton:hover { background:#E2EAF5; border-color:#2C5F8A; }
        QStatusBar { background:#EEF2F7; color:#555; font-size:11px; }
        QMenuBar { background:#2C5F8A; color:white; }
        QMenuBar::item { padding:4px 12px; }
        QMenuBar::item:selected { background:#3A78B5; }
        QMenu { background:white; border:1px solid #D0D5DD; }
        QMenu::item:selected { background:#EEF4FC; color:#2C5F8A; }
    """)

    from ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

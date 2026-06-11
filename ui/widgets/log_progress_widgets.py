"""
Widgets de monitoreo: LogWidget y ProgressWidget.

LogWidget:     muestra la salida de OpenFOAM en tiempo real.
ProgressWidget: barra de progreso con etiqueta del paso actual.
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QProgressBar, QLabel, QPushButton, QSizePolicy,
)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QFont, QColor, QTextCursor, QPalette


class LogWidget(QWidget):
    """
    Widget de log en tiempo real para la salida de OpenFOAM.

    Muestra cada línea con timestamp opcional.
    Permite limpiar el log y copiar su contenido.

    Args:
        max_lines:     Número máximo de líneas antes de truncar.
        show_timestamp: Si True, añade HH:MM:SS antes de cada línea.
        parent:        Widget padre.
    """

    def __init__(
        self,
        max_lines:      int  = 2000,
        show_timestamp: bool = False,
        parent:         QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_lines     = max_lines
        self._show_timestamp = show_timestamp
        self._line_count    = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Barra superior con título y botón limpiar
        top = QHBoxLayout()
        top.setContentsMargins(4, 2, 4, 2)

        lbl = QLabel("Log de simulación")
        lbl.setFont(QFont("Arial", 8, QFont.Bold))
        top.addWidget(lbl)
        top.addStretch()

        self._btn_clear = QPushButton("Limpiar")
        self._btn_clear.setFixedHeight(22)
        self._btn_clear.setFixedWidth(70)
        self._btn_clear.clicked.connect(self.clear)
        top.addWidget(self._btn_clear)

        layout.addLayout(top)

        # Área de texto
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Courier New", 9))
        self._text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Estilo oscuro tipo terminal
        palette = self._text.palette()
        palette.setColor(QPalette.Base, QColor("#1E1E1E"))
        palette.setColor(QPalette.Text, QColor("#D4D4D4"))
        self._text.setPalette(palette)
        self._text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)

        layout.addWidget(self._text)

    # ── API pública ───────────────────────────────────────────────────────────

    def append_log(self, message: str) -> None:
        """
        Añade una línea al log. Thread-safe via Qt event loop.

        Args:
            message: Texto a añadir. Se añade una nueva línea automáticamente.
        """
        if self._show_timestamp:
            ts  = QDateTime.currentDateTime().toString("HH:mm:ss")
            msg = f"[{ts}] {message}"
        else:
            msg = message

        # Colorear líneas especiales
        html = self._colorize(msg)
        self._text.append(html)

        # Truncar si excede el límite
        self._line_count += 1
        if self._line_count > self._max_lines:
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # eliminar salto de línea

        # Auto-scroll al final
        self._text.moveCursor(QTextCursor.End)

    def clear(self) -> None:
        """Limpia todo el contenido del log."""
        self._text.clear()
        self._line_count = 0

    def get_text(self) -> str:
        """Retorna el contenido completo del log como texto plano."""
        return self._text.toPlainText()

    def save_to_file(self, path: str) -> None:
        """Guarda el log en un archivo de texto."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.get_text())

    @staticmethod
    def _colorize(msg: str) -> str:
        """Aplica colores HTML a líneas especiales del log de OpenFOAM."""
        # Escapar caracteres HTML
        msg_html = (msg
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

        # Colorear por tipo de mensaje
        if any(k in msg for k in ("FOAM FATAL", "FOAM exiting", "✗", "Falló")):
            return f'<span style="color:#F44747;">{msg_html}</span>'
        elif any(k in msg for k in ("✓", "✅", "completado", "Completado")):
            return f'<span style="color:#4EC9B0;">{msg_html}</span>'
        elif any(k in msg for k in ("⚠", "Warning", "advertencia")):
            return f'<span style="color:#DCDCAA;">{msg_html}</span>'
        elif msg.strip().startswith("▶") or msg.strip().startswith("═"):
            return f'<span style="color:#569CD6;font-weight:bold;">{msg_html}</span>'
        elif "Time =" in msg or "ExecutionTime" in msg:
            return f'<span style="color:#9CDCFE;">{msg_html}</span>'
        else:
            return f'<span style="color:#D4D4D4;">{msg_html}</span>'


class ProgressWidget(QWidget):
    """
    Barra de progreso con etiqueta del paso actual y porcentaje.

    Args:
        parent: Widget padre.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Etiqueta del paso actual
        self._label_step = QLabel("Listo")
        self._label_step.setFont(QFont("Arial", 9))
        self._label_step.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._label_step)

        # Fila con barra + porcentaje
        row = QHBoxLayout()
        row.setSpacing(8)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(18)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                background-color: #2C5F8A;
                border-radius: 9px;
            }
        """)
        row.addWidget(self._bar, stretch=1)

        self._label_pct = QLabel("0%")
        self._label_pct.setFont(QFont("Arial", 9, QFont.Bold))
        self._label_pct.setFixedWidth(38)
        self._label_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self._label_pct)

        layout.addLayout(row)

    # ── API pública ───────────────────────────────────────────────────────────

    def update_progress(self, step: str, percent: float) -> None:
        """
        Actualiza el progreso. Thread-safe via Qt event loop.

        Args:
            step:    Nombre del paso actual (ej: "blockMesh").
            percent: Porcentaje de avance (0-100).
        """
        pct = int(max(0, min(100, percent)))
        self._bar.setValue(pct)
        self._label_pct.setText(f"{pct}%")
        self._label_step.setText(step)

    def reset(self) -> None:
        """Resetea la barra a cero."""
        self.update_progress("Listo", 0.0)

    def set_completed(self) -> None:
        """Muestra estado completado (100%)."""
        self.update_progress("✓ Completado", 100.0)
        self._bar.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                background-color: #1AA870;
                border-radius: 9px;
            }
        """)

    def set_error(self) -> None:
        """Muestra estado de error."""
        self._label_step.setText("✗ Error en la simulación")
        self._bar.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                background-color: #F44747;
                border-radius: 9px;
            }
        """)

"""Qt GUI frontend for rivalcfg CLI."""

import io
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout

from . import __main__ as rival_main


try:
    from PyQt5 import QtWidgets
except ImportError:  # pragma: no cover
    QtWidgets = None


class RivalcfgGui(QtWidgets.QWidget):
    """Simple Qt wrapper around the existing CLI entrypoint."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("rivalcfg (Qt GUI)")
        self.resize(850, 500)

        self.args_input = QtWidgets.QLineEdit()
        self.args_input.setPlaceholderText("Voorbeeld: --list of --help")

        self.run_button = QtWidgets.QPushButton("Uitvoeren")
        self.run_button.clicked.connect(self._on_run)

        self.clear_button = QtWidgets.QPushButton("Leeg")
        self.clear_button.clicked.connect(self._on_clear)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(QtWidgets.QLabel("CLI argumenten:"))
        top_layout.addWidget(self.args_input, 1)
        top_layout.addWidget(self.run_button)
        top_layout.addWidget(self.clear_button)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.addLayout(top_layout)
        root_layout.addWidget(self.output, 1)

    def _on_clear(self):
        self.output.clear()

    def _on_run(self):
        raw_args = self.args_input.text().strip()
        args = shlex.split(raw_args)
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                rival_main.main(args)
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1
        except Exception as exc:  # pragma: no cover
            stderr_buf.write(f"E: Unexpected error: {exc}\n")
            exit_code = 1

        stdout_text = stdout_buf.getvalue().strip()
        stderr_text = stderr_buf.getvalue().strip()

        if stdout_text:
            self.output.appendPlainText(stdout_text)
        if stderr_text:
            self.output.appendPlainText(stderr_text)

        self.output.appendPlainText(f"\n[Exit code: {exit_code}]\n")


def main():
    """Launch the Qt GUI."""
    if QtWidgets is None:
        raise RuntimeError(
            "PyQt5 is required to use the Qt GUI. Install it with: pip install PyQt5"
        )

    app = QtWidgets.QApplication(sys.argv)
    window = RivalcfgGui()
    window.show()
    return app.exec_()

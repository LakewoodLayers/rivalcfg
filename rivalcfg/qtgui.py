"""Qt GUI frontend for rivalcfg CLI."""

import io
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout

from . import __main__ as rival_main
from . import devices
from . import get_first_mouse


try:
    from PyQt5 import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    QtWidgets = None
    QtCore = None


class RivalcfgGui(QtWidgets.QWidget):
    """Qt frontend with basic SteelSeries GG-like controls for common settings."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("rivalcfg (Qt GUI)")
        self.resize(1000, 680)

        self.mouse = None
        self.mouse_profile = None
        self.sensitivity_cli = None
        self.polling_cli = None

        self._init_device()
        self._build_ui()

    def _init_device(self):
        try:
            self.mouse = get_first_mouse()
            if self.mouse:
                self.mouse_profile = devices.get_profile(
                    vendor_id=self.mouse.vendor_id,
                    product_id=self.mouse.product_id,
                )
        except Exception:
            self.mouse = None
            self.mouse_profile = None

    def _build_ui(self):
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)

        self.device_label = QtWidgets.QLabel(
            self.mouse.name if self.mouse else "No supported mouse detected"
        )

        quick_group = QtWidgets.QGroupBox("Quick actions")
        quick_layout = QtWidgets.QGridLayout(quick_group)
        self._add_action_button(quick_layout, 0, 0, "Help", ["--help"])
        self._add_action_button(quick_layout, 0, 1, "Version", ["--version"])
        self._add_action_button(quick_layout, 0, 2, "List devices", ["--list"])
        self._add_action_button(quick_layout, 1, 0, "Debug info", ["--print-debug"])
        self._add_action_button(quick_layout, 1, 1, "Print udev", ["--print-udev"])

        controls_group = QtWidgets.QGroupBox("Mouse controls")
        controls_layout = QtWidgets.QFormLayout(controls_group)

        self.no_save_checkbox = QtWidgets.QCheckBox("Do not save settings (--no-save)")
        self.reset_checkbox = QtWidgets.QCheckBox("Reset first (--reset)")
        controls_layout.addRow(self.no_save_checkbox)
        controls_layout.addRow(self.reset_checkbox)

        self.dpi1_slider = None
        self.dpi2_slider = None
        self.dpi1_value = None
        self.dpi2_value = None
        self.polling_combo = None

        self._build_setting_controls(controls_layout)

        self.extra_args_input = QtWidgets.QLineEdit()
        self.extra_args_input.setPlaceholderText("Optional advanced args")
        controls_layout.addRow("Extra args", self.extra_args_input)

        apply_button = QtWidgets.QPushButton("Apply settings")
        apply_button.clicked.connect(self._on_apply_settings)

        clear_button = QtWidgets.QPushButton("Clear output")
        clear_button.clicked.connect(self.output.clear)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.addWidget(QtWidgets.QLabel("Detected device:"))
        root_layout.addWidget(self.device_label)
        root_layout.addWidget(quick_group)
        root_layout.addWidget(controls_group)
        root_layout.addWidget(apply_button)
        root_layout.addWidget(clear_button)
        root_layout.addWidget(self.output, 1)

    def _build_setting_controls(self, form_layout):
        if not self.mouse_profile:
            return

        for setting_name, info in self.mouse_profile["settings"].items():
            if info.get("value_type") == "multidpi_range_choice" and not self.sensitivity_cli:
                self.sensitivity_cli = info["cli"][1]
                min_dpi, max_dpi, step = info["input_range"]
                default_values = [int(v.strip()) for v in str(info["default"]).split(",")[:2]]

                dpi_layout = QtWidgets.QHBoxLayout()
                self.dpi1_slider, self.dpi1_value = self._make_dpi_slider(
                    min_dpi, max_dpi, step, default_values[0]
                )
                self.dpi2_slider, self.dpi2_value = self._make_dpi_slider(
                    min_dpi, max_dpi, step, default_values[1]
                )
                dpi_layout.addWidget(QtWidgets.QLabel("DPI 1"))
                dpi_layout.addWidget(self.dpi1_slider)
                dpi_layout.addWidget(self.dpi1_value)
                dpi_layout.addWidget(QtWidgets.QLabel("DPI 2"))
                dpi_layout.addWidget(self.dpi2_slider)
                dpi_layout.addWidget(self.dpi2_value)
                dpi_widget = QtWidgets.QWidget()
                dpi_widget.setLayout(dpi_layout)
                form_layout.addRow("Sensitivity", dpi_widget)

            if setting_name == "polling_rate" and info.get("value_type") == "choice":
                self.polling_cli = info["cli"][1]
                self.polling_combo = QtWidgets.QComboBox()
                for choice in sorted(info["choices"].keys()):
                    self.polling_combo.addItem(str(choice), str(choice))
                form_layout.addRow("Polling rate (Hz)", self.polling_combo)

    def _make_dpi_slider(self, minimum, maximum, step, default_value):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setSingleStep(step)
        slider.setPageStep(step)
        slider.setTickInterval(step * 2)
        slider.setValue(default_value)

        label = QtWidgets.QLabel(str(default_value))
        slider.valueChanged.connect(lambda value: label.setText(str(value)))
        return slider, label

    def _add_action_button(self, layout, row, col, label, args):
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(lambda _checked=False, command_args=args: self._run(command_args))
        layout.addWidget(button, row, col)

    def _on_apply_settings(self):
        args = []
        if self.no_save_checkbox.isChecked():
            args.append("--no-save")
        if self.reset_checkbox.isChecked():
            args.append("--reset")

        if self.dpi1_slider and self.dpi2_slider and self.sensitivity_cli:
            args.extend(
                [
                    self.sensitivity_cli,
                    f"{self.dpi1_slider.value()},{self.dpi2_slider.value()}",
                ]
            )

        if self.polling_combo and self.polling_cli:
            args.extend([self.polling_cli, self.polling_combo.currentData()])

        extra_args = self.extra_args_input.text().strip()
        if extra_args:
            args.extend(shlex.split(extra_args))

        self._run(args)

    def _run(self, args):
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

        self.output.appendPlainText(f"$ rivalcfg {' '.join(args)}")
        if stdout_buf.getvalue().strip():
            self.output.appendPlainText(stdout_buf.getvalue().strip())
        if stderr_buf.getvalue().strip():
            self.output.appendPlainText(stderr_buf.getvalue().strip())
        self.output.appendPlainText(f"[Exit code: {exit_code}]\n")


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

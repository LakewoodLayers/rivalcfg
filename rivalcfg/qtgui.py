"""Qt GUI frontend for rivalcfg CLI."""

import io
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
    """Qt frontend with slider/dropdown/color controls for common settings."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("rivalcfg (Qt GUI)")
        self.resize(1060, 720)

        self.mouse = None
        self.mouse_profile = None

        self.sensitivity_cli = None
        self.polling_cli = None
        self.effect_cli = None
        self.zone_color_controls = []

        self.dpi1_slider = None
        self.dpi2_slider = None
        self.dpi1_value = None
        self.dpi2_value = None
        self.polling_combo = None
        self.effect_combo = None

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

        detected = self.mouse.name if self.mouse else "No supported mouse detected"
        self.device_label = QtWidgets.QLabel(detected)

        self.no_save_checkbox = QtWidgets.QCheckBox("Do not save settings (--no-save)")
        self.reset_checkbox = QtWidgets.QCheckBox("Reset first (--reset)")

        quick_group = QtWidgets.QGroupBox("Quick actions")
        quick_layout = QtWidgets.QGridLayout(quick_group)
        self._add_action_button(quick_layout, 0, 0, "Help", ["--help"])
        self._add_action_button(quick_layout, 0, 1, "Version", ["--version"])
        self._add_action_button(quick_layout, 0, 2, "List devices", ["--list"])
        self._add_action_button(quick_layout, 1, 0, "Debug info", ["--print-debug"])
        self._add_action_button(quick_layout, 1, 1, "Print udev", ["--print-udev"])

        controls_group = QtWidgets.QGroupBox("Mouse controls")
        controls_layout = QtWidgets.QFormLayout(controls_group)
        controls_layout.addRow(self.no_save_checkbox)
        controls_layout.addRow(self.reset_checkbox)
        self._build_setting_controls(controls_layout)

        apply_button = QtWidgets.QPushButton("Apply settings")
        apply_button.clicked.connect(self._on_apply_settings)

        clear_button = QtWidgets.QPushButton("Clear output")
        clear_button.clicked.connect(self.output.clear)

        root = QtWidgets.QVBoxLayout(self)
        root.addWidget(QtWidgets.QLabel("Detected device:"))
        root.addWidget(self.device_label)
        root.addWidget(quick_group)
        root.addWidget(controls_group)
        root.addWidget(apply_button)
        root.addWidget(clear_button)
        root.addWidget(self.output, 1)

    def _build_setting_controls(self, form_layout):
        if not self.mouse_profile:
            return

        for setting_name, info in self.mouse_profile["settings"].items():
            if info.get("value_type") == "multidpi_range_choice" and not self.sensitivity_cli:
                self.sensitivity_cli = info["cli"][1]
                min_dpi, max_dpi, step = info["input_range"]
                defaults = [int(v.strip()) for v in str(info["default"]).split(",")[:2]]
                dpi_layout = QtWidgets.QHBoxLayout()
                self.dpi1_slider, self.dpi1_value = self._make_dpi_slider(
                    min_dpi, max_dpi, step, defaults[0]
                )
                self.dpi2_slider, self.dpi2_value = self._make_dpi_slider(
                    min_dpi, max_dpi, step, defaults[1]
                )
                dpi_layout.addWidget(QtWidgets.QLabel("DPI 1"))
                dpi_layout.addWidget(self.dpi1_slider)
                dpi_layout.addWidget(self.dpi1_value)
                dpi_layout.addWidget(QtWidgets.QLabel("DPI 2"))
                dpi_layout.addWidget(self.dpi2_slider)
                dpi_layout.addWidget(self.dpi2_value)
                holder = QtWidgets.QWidget()
                holder.setLayout(dpi_layout)
                form_layout.addRow("Sensitivity", holder)

            if setting_name == "polling_rate" and info.get("value_type") == "choice":
                self.polling_cli = info["cli"][1]
                self.polling_combo = QtWidgets.QComboBox()
                for choice in sorted(info["choices"].keys()):
                    self.polling_combo.addItem(str(choice), str(choice))
                if "default" in info:
                    index = self.polling_combo.findData(str(info["default"]))
                    if index >= 0:
                        self.polling_combo.setCurrentIndex(index)
                form_layout.addRow("Polling rate (Hz)", self.polling_combo)

            if setting_name == "light_effect" and info.get("value_type") == "choice":
                self.effect_cli = info["cli"][1]
                self.effect_combo = QtWidgets.QComboBox()
                for choice in info["choices"].keys():
                    self.effect_combo.addItem(str(choice), str(choice))
                if "default" in info:
                    index = self.effect_combo.findData(str(info["default"]))
                    if index >= 0:
                        self.effect_combo.setCurrentIndex(index)
                form_layout.addRow("Light effect", self.effect_combo)

            if info.get("value_type") == "rgbcolor":
                self._add_color_control(form_layout, setting_name, info)

    def _add_color_control(self, form_layout, setting_name, setting_info):
        cli_option = setting_info["cli"][0]
        default = str(setting_info.get("default", "#ffffff"))

        color_btn = QtWidgets.QPushButton(default)
        color_btn.setFixedWidth(90)
        self._set_color_button_style(color_btn, default)

        color_text = QtWidgets.QLineEdit(default)
        color_text.setFixedWidth(110)

        color_btn.clicked.connect(lambda: self._pick_color(color_btn, color_text))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(color_btn)
        row.addWidget(color_text)
        row.addStretch(1)

        holder = QtWidgets.QWidget()
        holder.setLayout(row)
        label = setting_info.get("label", setting_name)
        form_layout.addRow(label, holder)

        self.zone_color_controls.append((cli_option, color_text))

    def _pick_color(self, button, color_text):
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        color_name = color.name()
        color_text.setText(color_name)
        self._set_color_button_style(button, color_name)

    def _set_color_button_style(self, button, color_name):
        button.setText(color_name)
        button.setStyleSheet("QPushButton { background-color: %s; }" % color_name)

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
        button.clicked.connect(lambda _checked=False, cmd_args=args: self._run(cmd_args))
        layout.addWidget(button, row, col)

    def _on_apply_settings(self):
        args = []
        if self.no_save_checkbox.isChecked():
            args.append("--no-save")
        if self.reset_checkbox.isChecked():
            args.append("--reset")

        if self.dpi1_slider and self.dpi2_slider and self.sensitivity_cli:
            args.extend(
                [self.sensitivity_cli, f"{self.dpi1_slider.value()},{self.dpi2_slider.value()}"]
            )

        if self.polling_combo and self.polling_cli:
            args.extend([self.polling_cli, self.polling_combo.currentData()])

        if self.effect_combo and self.effect_cli:
            args.extend([self.effect_cli, self.effect_combo.currentData()])

        for cli_option, text_widget in self.zone_color_controls:
            value = text_widget.text().strip()
            if value:
                args.extend([cli_option, value])

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
        out = stdout_buf.getvalue().strip()
        err = stderr_buf.getvalue().strip()
        if out:
            self.output.appendPlainText(out)
        if err:
            self.output.appendPlainText(err)
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

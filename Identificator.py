# Copyright (c) 2025 Sanoscorb

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import re
import sys
import shutil
import argparse
import subprocess
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QFileDialog,
    QAction,
    QMenu
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

REGEX_GET_ID = r"^(.+?)-\d+\..+$"
REGEX_GET_NUM = r"^.+?-(\d+)\..+$"

class App(QWidget):
    def __init__(self, parsed_args):
        super().__init__()
        self.setFixedSize(250, 85)

        if os.path.isdir(parsed_args.destination):
            self.dest_dir = os.path.abspath(parsed_args.destination)
        else:
            self.dest_dir = QFileDialog.getExistingDirectory(self, "Select a directory")

        if not self.dest_dir:
            self.forced_exit()
            return

        self.setWindowTitle(f"To: {os.path.basename(self.dest_dir)}")

        self.prev_files = [os.path.abspath(file) for file in parsed_args.files]
        if any(not os.path.isfile(file) for file in self.prev_files) or not self.prev_files:
            self.prev_files, _ = QFileDialog.getOpenFileNames(self, "Select a files to rename")

        if not self.prev_files:
            message = ("You have not selected any files.\n"
                       "The renaming function will not be available.")
            QMessageBox.information(None, "Information", message)

        self.new_files = []
        self.identifiers = []
        self.busy_numbers = {}
        
        self.get_identifiers()

        layout = QVBoxLayout()

        label = QLabel("Select the identifier:")
        layout.addWidget(label)

        self.combobox = QComboBox()
        self.combobox.addItems(self.identifiers)
        self.combobox.setEditable(True)
        self.combobox.setFocus()
        self.combobox.lineEdit().selectAll()
        self.combobox.lineEdit().returnPressed.connect(self.rename_files)
        layout.addWidget(self.combobox)

        button_layout = QHBoxLayout()

        open_button = QPushButton("Open")
        open_menu = QMenu()

        self.explorer_action = QAction("In Explorer")
        self.explorer_action.triggered.connect(self.open_explorer)
        open_menu.addAction(self.explorer_action)

        self.file_action = QAction("As file")
        self.file_action.triggered.connect(self.open_explorer)
        open_menu.addAction(self.file_action)

        open_button.setMenu(open_menu)
        button_layout.addWidget(open_button)

        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self.rename_files)
        button_layout.addWidget(rename_button)
        if not self.prev_files:
            rename_button.setEnabled(False)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def rename_files(self):
        identifier = self.combobox.currentText()
        if identifier == "":
            QMessageBox.information(self, "Information", "Please select an identifier!")
            return

        identifier = identifier.strip()
        self.get_busy_numbers(identifier)
        used = set(self.busy_numbers.get(identifier, []))
        free_numbers = []
        current = 1
        while len(free_numbers) < len(self.prev_files):
            if current not in used:
                free_numbers.append(current)
            current += 1

        self.new_files = [
            os.path.join(self.dest_dir, f"{identifier}-{num}{os.path.splitext(file)[1]}")
            for file, num in zip(self.prev_files, free_numbers)
        ]

        details = ""
        for i in range(len(self.prev_files)):
            details += f"{self.prev_files[i]} -\u2060> {self.new_files[i]}\n"

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Are you sure? The action cannot be undone!")
        msg.setInformativeText("The following files will be renamed:")
        msg.setDetailedText(details)
        msg.setWindowTitle("Warning!")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setStyleSheet("QTextEdit { font-family: 'Consolas'; font-size: 9pt; }")
        [button.click() for button in msg.buttons() if msg.buttonRole(button) == QMessageBox.ActionRole]

        result = msg.exec_()

        if result == QMessageBox.Yes:
            for i in range(len(self.prev_files)):
                try:
                    shutil.move(self.prev_files[i], self.new_files[i])
                except Exception as e:
                    message = (f"Error while renaming files:\n"
                               f"\"{self.prev_files[i]}\" -> \"{self.new_files[i]}\"\n\n"
                               f"{type(e)}: {e}")
                    QMessageBox.critical(self, "Error!", message)
            QMessageBox.information(self, "Information", "Done!")
            self.close()
        else:
            QMessageBox.information(self, "Information", "Cancel!")

    def open_explorer(self):
        identifier = self.combobox.currentText()
        try:
            if identifier not in self.busy_numbers:
                self.get_busy_numbers(identifier)
            for file in os.listdir(self.dest_dir):
                if file.startswith(f"{identifier}-{self.busy_numbers[identifier][0]}"):
                    path = os.path.join(self.dest_dir, file).replace("/", "\\")
                    match self.sender():
                        case self.explorer_action:
                            subprocess.run(["explorer", "/select,", path])
                        case self.file_action:
                            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

                    break
        except IndexError:
            QMessageBox.critical(self, "Error!", "This identifier is not in the directory")
        except Exception as e:
            self.msgbox_error(e)

    def get_identifiers(self):
        regex = re.compile(REGEX_GET_ID)
        for file in os.listdir(self.dest_dir):
            if match := regex.match(file):
                identifier = match.group(1).strip()
                if identifier not in self.identifiers:
                    self.identifiers.append(identifier)

    def get_busy_numbers(self, identifier):
        regex = re.compile(REGEX_GET_NUM)
        if identifier not in self.busy_numbers:
            self.busy_numbers[identifier] = [
                int(match.group(1)) 
                for file in os.listdir(self.dest_dir)
                if (match := regex.match(file))
                and file.startswith(f"{identifier}-")
            ]

    def msgbox_error(self, e):
        QMessageBox.critical(self, "Error!", f"{type(e)}: {e}")

    def forced_exit(self):
        self.close()
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Changes the file name from the pattern."
    )

    parser.add_argument("-d", "--destination", type=str, default="",
        help="Destination directory."
    )

    parser.add_argument("-f", "--files", type=str, nargs="+", default=[],
        help="List of files to rename."
    )

    args = parser.parse_args()

    app = QApplication(sys.argv)
    ex = App(args)
    ex.show()
    sys.exit(app.exec_())
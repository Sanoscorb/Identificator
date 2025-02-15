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
    QFileDialog
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
            self.dest_dir = QFileDialog.getExistingDirectory(self, "Select Directory")

        if not self.dest_dir:
            self.forced_exit()
            return

        self.setWindowTitle(f"To: {os.path.basename(self.dest_dir)}")

        self.prev_files = [os.path.abspath(file) for file in parsed_args.files]
        if any(not os.path.isfile(file) for file in self.prev_files) or not self.prev_files:
            self.prev_files, _ = QFileDialog.getOpenFileNames(self, "Select files to rename")

        if not self.prev_files:
            message = ("You have not selected any files.\n"
                       "The renaming function will not be available.")
            QMessageBox.information(None, "Information", message)

        self.new_files = []
        self.authors = []
        self.busy_numbers = {}
        
        self.get_authors()

        layout = QVBoxLayout()

        label = QLabel("Select the author:")
        layout.addWidget(label)

        self.combobox = QComboBox()
        self.combobox.addItems(self.authors)
        self.combobox.setEditable(True)
        layout.addWidget(self.combobox)

        button_layout = QHBoxLayout()

        open_button = QPushButton("Open")
        open_button.clicked.connect(self.open_explorer)
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
        author = self.combobox.currentText()
        if author == "":
            QMessageBox.information(self, "Information", "Please select an author!")
            return

        author = author.strip()
        self.get_busy_numbers(author)
        used = set(self.busy_numbers.get(author, []))
        free_numbers = []
        current = 1
        while len(free_numbers) < len(self.prev_files):
            if current not in used:
                free_numbers.append(current)
            current += 1

        self.new_files = [
            os.path.join(self.dest_dir, f"{author}-{num}{os.path.splitext(file)[1]}")
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
            try:
                for i in range(len(self.prev_files)):
                    shutil.move(self.prev_files[i], self.new_files[i])
                QMessageBox.information(self, "Information", "Done!")
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                self.forced_exit()
        else:
            QMessageBox.information(self, "Information", "Cancel!")

    def open_explorer(self):
        author = self.combobox.currentText()
        if author:
            try:
                if author not in self.busy_numbers:
                    self.get_busy_numbers(author)
                for file in os.listdir(self.dest_dir):
                    if file.startswith(f"{author}-{self.busy_numbers[author][0]}"):
                        path = os.path.join(self.dest_dir, file).replace("/", "\\")
                        subprocess.run(["explorer", "/select,", path])
                        break
            except IndexError:
                QMessageBox.critical(self, "Error!", "This author is not in the directory")
            except Exception as e:
                QMessageBox.critical(self, "Error!", str(e))

    def get_authors(self):
        regex = re.compile(REGEX_GET_ID)
        for file in os.listdir(self.dest_dir):
            if match := regex.match(file):
                author = match.group(1).strip()
                if author not in self.authors:
                    self.authors.append(author)

        self.authors.sort()

    def get_busy_numbers(self, author):
        regex = re.compile(REGEX_GET_NUM)
        if author not in self.busy_numbers:
            self.busy_numbers[author] = [
                int(match.group(1)) 
                for file in os.listdir(self.dest_dir)
                if (match := regex.match(file))
                and file.startswith(f"{author}-")
            ]

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
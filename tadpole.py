from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QMessageBox, QGridLayout, QLabel, QComboBox, QPushButton)
from PyQt5.QtGui import (QIcon)
import frogtool
import os
import sys
import string

def RunFrogTool():
    drive = window.combobox_drive.currentText()
    console = window.combobox_console.currentText()
    
    print(f"Running Frogtool with drive ({drive}) and console ({console})")
    result = frogtool.process_sys(drive,console, False)
    QMessageBox.about(window,"Result",result)

#SubClass QMainWindow to create a Tadpole general interface
class MainWindow (QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tadpole - SF2000 Tool")
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QGridLayout(widget)
        rowCounter = 0
        
        #Drive Select Widgets
        self.lbl_drive = QLabel(text="Drive:")     
        self.combobox_drive = QComboBox()
        layout.addWidget(self.lbl_drive, rowCounter, 0)
        layout.addWidget(self.combobox_drive, rowCounter, 1)
        rowCounter += 1
        
        #Console Select Widgets
        self.lbl_console = QLabel(text="Console:")
        self.combobox_console = QComboBox()
        layout.addWidget(self.lbl_console, rowCounter, 0)
        layout.addWidget(self.combobox_console, rowCounter, 1)  
        rowCounter += 1
        
        #Update Widget
        self.button = QPushButton("Update!")
        layout.addWidget(self.button, rowCounter, 0)
   


#Initialise the Application
app = QApplication(sys.argv)

# Build the Window
window = MainWindow()

#Update list of drives
available_drives_placeholder = "???"
window.combobox_drive.addItem(QIcon(),available_drives_placeholder,available_drives_placeholder)
available_drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
window.combobox_drive.clear()
for drive in available_drives:
    window.combobox_drive.addItem(QIcon(),drive,drive)


#Update list of consoles
available_consoles_placeholder = "???"
window.combobox_console.addItem(QIcon(),available_consoles_placeholder,available_consoles_placeholder)
window.combobox_console.clear()
for console in frogtool.systems.keys():
    window.combobox_console.addItem(QIcon(),console,console)


window.button.clicked.connect(RunFrogTool)


window.show()
app.exec()
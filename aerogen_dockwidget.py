# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AeroGenDockWidget
                                 A QGIS plugin
 AeroGen Plugin
                             -------------------
        begin                : 2017-04-24
        git sha              : $Format:%H$
        copyright            : (C) 2017 by CTU GeoForAll Lab
        email                : martin.landa@fsv.cvut.cz
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, SIGNAL, QSettings

from qgis.gui import QgsMessageBar
from qgis.utils import iface

from reader import AreaReader, AreaReaderError

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'aerogen_dockwidget_base.ui'))


class AeroGenDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(AeroGenDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # settings
        self._settings = QSettings()

        self.connect(self.browseButton,
                     SIGNAL("clicked()"), self.OnBrowse)
        self.connect(self.generateButton,
                     SIGNAL("clicked()"), self.OnGenerate)
        
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def OnBrowse(self):
        sender = 'AeroGen-{}-lastUserFilePath'.format(self.sender().objectName())
        lastPath = self._settings.value(sender, '')

        filePath = QtGui.QFileDialog.getOpenFileName(self, self.tr("Load XYZ file"),
                                                     lastPath, self.tr("XYZ file (*.xyz)"))
        if not filePath:
            # action canceled
            return

        filePath = os.path.normpath(filePath)
        self.textInput.setText(filePath)
        
        # remember directory path
        self._settings.setValue(sender, os.path.dirname(filePath))

    def OnGenerate(self):
        try:
            ar = AreaReader(self.textInput.toPlainText())
            print ar.area_polygon()
        except AreaReaderError as e:
            iface.messageBar().pushMessage("Error",
                                           "{}".format(e),
                                           level=QgsMessageBar.CRITICAL
            )

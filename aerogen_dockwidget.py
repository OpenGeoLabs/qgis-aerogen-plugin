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
from qgis.core import QgsMapLayerRegistry, QgsCoordinateReferenceSystem
from qgis.utils import iface

from reader import AerogenReader, AerogenReaderError, AerogenReaderCRS
from exceptions import AerogenError
from aerogen_layer import AerogenLayer

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

        # reader
        self._ar = None
        self._rsCrs = None

        self.connect(self.browseButton,
                     SIGNAL("clicked()"), self.OnBrowse)
        self.connect(self.generateButton,
                     SIGNAL("clicked()"), self.OnGenerate)

        # disable some widgets
        self.crsButton.setEnabled(False)
        self.outputButton.setEnabled(False)
        self.generateButton.setEnabled(False)
        
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def OnBrowse(self):
        sender = 'AeroGen-{}-lastUserFilePath'.format(self.sender().objectName())
        # load lastly used directory path
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

        # read input file
        try:
            self._ar = AerogenReader(filePath)
            crs = self._ar.crs()
            self.crsButton.setEnabled(True)
            self.outputButton.setEnabled(True)
            self.generateButton.setEnabled(True)
        except AerogenReaderError as e:
            iface.messageBar().pushMessage(
                "Error",
                "{}".format(e),
                level=QgsMessageBar.CRITICAL
            )
            return
        except AerogenReaderCRS as e:
            iface.messageBar().pushMessage(
                "Info",
                self.tr("{}. You need to define CRS manually.").format(e),
                level=QgsMessageBar.INFO
            )
            self.crsButton.setEnabled(True)
            return

        # autodetect CRS by EPSG code
        self._rsCrs = QgsCoordinateReferenceSystem(crs,
                                                   QgsCoordinateReferenceSystem.EpsgCrsId)
        self.crsLabel.setText(self._rsCrs.description())

        # set default output path
        self.textOutput.setText(os.path.dirname(filePath))

    def OnGenerate(self):
        if not self._ar:
            return

        output_dir = self.textOutput.toPlainText()
        try:
            # create a new Shapefile layer from area polygon
            output_file = os.path.join(output_dir, self._ar.basename() + '_area.shp')
            polygon_layer = AerogenLayer(output_file, self._ar.area(), self._rsCrs)
            # add map layer to the canvas
            QgsMapLayerRegistry.instance().addMapLayer(polygon_layer)

            # create a new Shapefile layer from survey line
            output_file = os.path.join(output_dir, self._ar.basename() + '_sl.shp')
            sl_layer = AerogenLayer(output_file, self._ar.sl(), self._rsCrs)
            # add map layer to the canvas
            QgsMapLayerRegistry.instance().addMapLayer(sl_layer)

        except AerogenReaderError as e:
            iface.messageBar().pushMessage("Error",
                                           "{}".format(e),
                                           level=QgsMessageBar.CRITICAL
            )

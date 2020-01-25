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

from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtCore import pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QDockWidget, QFileDialog

from qgis.gui import QgsMessageBar
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsVectorFileWriter, QgsWkbTypes
from qgis.utils import iface

from .reader import AerogenReader, AerogenReaderError, AerogenReaderCRS
from .exceptions import AerogenError
from .aerogen_layer import AerogenLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'aerogen_dockwidget_base.ui'))


class AeroGenDockWidget(QDockWidget, FORM_CLASS):

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
        self._destCrs = None

        self.browseButton.clicked.connect(self.OnBrowseInput)
        self.generateButton.clicked.connect(self.OnGenerate)
        self.outputButton.clicked.connect(self.OnBrowseOutput)

        # disable some widgets
        self.crsButton.setVisible(False)
        self.outputButton.setEnabled(False)
        self.generateButton.setEnabled(False)
        
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def OnBrowseInput(self):
        sender = 'AeroGen-{}-lastUserFilePath'.format(self.sender().objectName())
        # load lastly used directory path
        lastPath = self._settings.value(sender, '')

        # filePath = QFileDialog.getOpenFileName(self, self.tr("Load XYZ file"),
        #                                              lastPath, self.tr("XYZ file (*.xyz)"))


        directoryPath = QFileDialog.getExistingDirectory(self, self.tr("Directory with XYZ files"),
                                                     lastPath)

        if not directoryPath:
            # action canceled
            return

        directoryPath = os.path.normpath(directoryPath)
        filePath = os.path.join(directoryPath, self._getMainXyzFile(directoryPath))
        self.textInput.setText(filePath)
        
        # remember directory path
        self._settings.setValue(sender, os.path.dirname(filePath))

        # set 4326 crs for output files
        self._destCrs = QgsCoordinateReferenceSystem(4326,
                                                     QgsCoordinateReferenceSystem.EpsgCrsId)

        # set default output path
        self.textOutput.setText(directoryPath)

        # read input file
        try:
            self._ar = AerogenReader(filePath)
            crs = self._ar.crs()
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
            self.crsButton.setVisible(True)
            self.crsButton.setEnabled(True)
            return

        # autodetect CRS by EPSG code
        self._rsCrs = QgsCoordinateReferenceSystem(crs,
                                                   QgsCoordinateReferenceSystem.EpsgCrsId)
        self.crsLabel.setText(self._rsCrs.description())

    def OnGenerate(self):
        if not self._ar:
            return

        output_dir = self.textOutput.toPlainText()
        try:
            for name, fn in (('polygon', self._ar.area),
                             ('survey_lines', self._ar.sl),
                             ('tie_lines', self._ar.tl)):
                # create a new Shapefile layer
                output_file = os.path.join(output_dir, self._ar.basename() + '_{}.shp'.format(name))
                if name == 'polygon':
                    layer = AerogenLayer(output_file, fn(), self._rsCrs)
                else:
                    layer = AerogenLayer(output_file, fn(), self._destCrs)
                layer.loadNamedStyle(self.stylePath(name))
                # add map layer to the canvas
                QgsProject.instance().addMapLayer(layer)
                if self.checkBoxGpx.isChecked():
                    if layer.geometryType() == QgsWkbTypes.LineGeometry:
                        # generate gpx output also for tie and survey lines
                        output_file_gpx = os.path.join(output_dir, self._ar.basename() + '_{}.gpx'.format(name))
                        QgsVectorFileWriter.writeAsVectorFormat(layer = layer,
                                                                fileName = output_file_gpx,
                                                                driverName = "GPX",
                                                                fileEncoding = "UTF-8",
                                                                destCRS = QgsCoordinateReferenceSystem(4326),
                                                                layerOptions = ["FORCE_GPX_TRACK = YES"],
                                                                skipAttributeCreation = True
                        )
        except (AerogenReaderError, AerogenError) as e:
            iface.messageBar().pushMessage("Error",
                                           "{}".format(e),
                                           level=QgsMessageBar.CRITICAL
            )

    def OnBrowseOutput(self):
        sender = 'AeroGen-{}-lastUserOutputFilePath'.format(self.sender().objectName())
        # load lastly used directory path
        lastPath = self._settings.value(sender, self.textInput.toPlainText())

        filePath = QtGui.QFileDialog.getExistingDirectory(self, self.tr('Choose Directory'), lastPath)
        if not filePath:
            # action canceled
            return

        filePath = os.path.normpath(filePath)
        self.textOutput.setText(filePath)

        # remember directory path
        self._settings.setValue(sender, os.path.dirname(filePath))

    def stylePath(self, name):
        stylePath = os.path.join(os.path.dirname(__file__), "style", name + '.qml')
        if not os.path.isfile(stylePath):
            raise AerogenError(self.tr("Style '{}' not found").format(styleName))

        return stylePath

    def _getMainXyzFile(self, directoryPath):
        for filename in os.listdir(directoryPath):
            if filename.endswith(".xyz"):
                try:
                    with open(os.path.join(directoryPath, filename)) as f:
                        line = f.readline()
                        # Not a nice detection, but if we base the detection of the main file
                        # on the filename it may be even worse
                        if line.startswith('UTM'):
                            return filename
                except:
                    raise AerogenError(self.tr("Directory is corrupted. The file '{}' can not be read").format(filename))


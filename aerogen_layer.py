import os

from qgis.core import QgsVectorLayer, QgsFeature, QgsVectorFileWriter, QGis
from exceptions import AerogenError

class AerogenLayer(QgsVectorLayer):
    def __init__(self, filename, geometries):
        """Aerogen Shapefile layer.
        """
        self.filename = filename
        name = os.path.splitext(os.path.basename(filename))[0]

        layer = self._createLayer(name, geometries)
        self._writeAsShapefile(layer, filename)

        super(AerogenLayer, self).__init__(filename,
                                           name, "ogr")
        
    def _createLayer(self, name, geometries):
        if len(geometries) < 1:
            raise AerogenError(self.tr("No features to write"))
        geom_type = geometries[0].wkbType()
        if geom_type == QGis.WKBPolygon:
            geom_strtype = 'Polygon'
        else:
            raise AerogenError(self.tr("Unsupported geometry type"))
        layer = QgsVectorLayer(geom_strtype, name,
                               'memory')
        
        features = []
        for geom in geometries:
            fet = QgsFeature()
            fet.setGeometry(geom)
            features.append(fet)
        layer.dataProvider().addFeatures(features)

        return layer
        
    def _writeAsShapefile(self, layer, filename):
        # write layer as Shapefile
        error = QgsVectorFileWriter.writeAsVectorFormat(layer,
                                                        filename,
                                                        "UTF-8",
                                                        None,
                                                        "ESRI Shapefile")
        if error != QgsVectorFileWriter.NoError:
            raise AerogenError(
                self.tr("Unable to write Aerogen layer into Esri Shapefile format.")
            )

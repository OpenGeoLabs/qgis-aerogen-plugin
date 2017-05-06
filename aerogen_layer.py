import os

from qgis.core import QgsVectorLayer, QgsFeature, QgsVectorFileWriter, QgsFields
from exceptions import AerogenError

class AerogenLayer(QgsVectorLayer):
    def __init__(self, filename, geometries, crs=None):
        """Aerogen Shapefile layer.
        """
        name = os.path.splitext(os.path.basename(filename))[0]

        layer = self._createLayer(filename, crs, geometries)

        super(AerogenLayer, self).__init__(filename,
                                           name, "ogr")

    def _createLayer(self, filename, crs, geometries):
        if len(geometries) < 1:
            raise AerogenError(self.tr("No features to write"))
        geom_type = geometries[0].wkbType()

        writer = QgsVectorFileWriter(filename, "UTF-8", QgsFields(),
                                     geom_type, crs, "ESRI Shapefile")

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise AerogenError(
                'Failed creating Shapefile: {}'.format(writer.errorMessage())
            )

        for geom in geometries:
            fet = QgsFeature()
            fet.setGeometry(geom)
            writer.addFeature(fet)

from qgis.core import QgsGeometry, QgsPoint

class AreaReaderError(Exception):
    pass

class AreaReader(object):
    def __init__(self, filename):
        polygon_points = []
        try:
            with open(filename) as f:
                for line in f.readlines():
                    if line.startswith('c;'): # polygon definition
                        p = line.split(';')
                        polygon_points.append(QgsPoint(
                            float(p[1].strip()), float(p[2].strip())
                        ))
        except IOError as e:
            raise AreaReaderError(e)

        if len(polygon_points) < 3:
            raise AreaReaderError("Unable to generate area polygon")
        else:
            # close polygon
            polygon_points.append(polygon_points[0])

        self._area_polygon = QgsGeometry.fromPolygon([polygon_points])

    def area_polygon(self):
        return self._area_polygon

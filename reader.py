import os
import math

from qgis.core import QgsGeometry, QgsPoint

class AerogenReaderError(Exception):
    pass

class AerogenReaderCRS(Exception):
    pass

class AerogenReader(object):
    def __init__(self, filename):
        self._basename = os.path.splitext(os.path.basename(filename))[0]

        self._crs = self._cm = self._ns = None
        self._polygon_points = []
        self._line_points = []

        try:
            with open(filename) as f:
                for line in f.readlines():
                    line = line.rstrip('\n').strip()
                    # try to detect CRS
                    if 'L1' in line:
                        self._crs = line.split(';', 1)[0]
                    if line.endswith('CM'):
                        self._cm = int(line.split(';', 1)[0])
                    if line.endswith('Lon'):
                        self._ns = float(line.split(';', 1)[0]) > 0

                    # read coordinates
                    if line.startswith('c;'):    # polygon definition
                        p = line.split(';')
                        self._polygon_points.append(
                            self._build_point(p[1], p[2])
                        )
                    elif line.startswith('l li'): # line definition
                        p = line.split(';')
                        self._line_points.append(
                            self._build_point(p[1], p[2])
                        )
                        self._line_points.append(
                            self._build_point(p[3], p[4])
                        )

        except IOError as e:
            raise AerogenReaderError(e)

    def _build_point(self, x, y):
        return QgsPoint(
            float(x.strip()), float(y.strip())
        )

    def area(self):
        if len(self._polygon_points) < 3:
            raise AerogenReaderError("Unable to generate polygon geometry")

        # close polygon
        self._polygon_points.append(self._polygon_points[0])

        return [QgsGeometry.fromPolygon([self._polygon_points])]

    def sl(self):
        if len(self._line_points) < 2:
            raise AerogenReaderError("Unable to generate line geometry")

        return [QgsGeometry.fromPolyline(self._line_points)]

    def tl(self):
        pass

    def crs(self):
        """Detect Coordinate Reference System."""
        if self._crs == 'UTM':
            if self._cm is None:
                raise AerogenReaderCRS("Unable to UTM zone")
            zone = int(math.floor((self._cm + 180)/6) % 60) + 1
            ns = 6 if self._ns else 7

            # return EPSG code
            return int('32{}{}'.format(ns, zone))

        raise AerogenReaderCRS("Unable to detect CRS")

    def basename(self):
        return self._basename

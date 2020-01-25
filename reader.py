import os
import math

from qgis.core import QgsGeometry, QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject

class AerogenReaderError(Exception):
    pass

class AerogenReaderCRS(Exception):
    pass

class AerogenReader(object):
    def __init__(self, filename):
        def line_value(line, cast_fn=None):
            value = line.split(';', 1)[0]
            if cast_fn:
                if ',' in value:
                    value = value.replace(',', '.')
                value = cast_fn(value)

            return value

        self._dirname = os.path.splitext(os.path.dirname(filename))[0]
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
                        self._crs = line_value(line)
                    if line.endswith('CM'):
                        self._cm = line_value(line, cast_fn=int)
                    if line.endswith('Lat'):
                        self._ns = line_value(line, cast_fn=float) > 0
                    if line.endswith('HSL'):
                        self._hsl = line_value(line, cast_fn=int) * (math.pi / 180) # rad
                    if line.endswith('spacing SL'):
                        self._ssl = line_value(line, cast_fn=float)
                    if line.endswith('HTL'):
                        self._htl = line_value(line, cast_fn=int) * (math.pi / 180) # rad
                    if line.endswith('spacing TL'):
                        self._stl = line_value(line, cast_fn=float)

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
        return QgsPointXY(
            float(x.strip()), float(y.strip())
        )

    def area(self):
        if len(self._polygon_points) < 3:
            raise AerogenReaderError("Unable to generate polygon geometry")

        # close polygon
        self._polygon_points.append(self._polygon_points[0])

        return [QgsGeometry.fromPolygonXY([self._polygon_points])]

    def sl(self):
        print("SL", self._basename, self._dirname)
        return [self._get_lines('sl')]

    def tl(self):
        print("TL", self._basename, self._dirname)
        return [self._get_lines('tl')]

    def _get_id(self, line):
        return line.split()[1]

    def _get_point_by_distance(self, line, last_point):
        """Returns point with key as a distance from point defined in last_point parameter."""
        items = line.split()
        current_point = self._build_point(items[2], items[3])
        distance = current_point.distance(last_point)
        return {distance: [items[2], items[3]]}

    def _get_point_by_id(self, line):
        """Returns point with key as an id from the file."""
        items = line.split()
        return {items[4]: [items[2], items[3]]}

    def _get_lines(self, type):
        # Open the file with read only permit
        f = open(self._dirname + "/" + self._basename + "_" + type + ".xyz", "r")
        lines = f.readlines()
        f.close()
        points = {}
        id = ''
        line_points = []
        for line in lines:
            line = ' '.join(line.split())
            if line.startswith('Line'):
                if id != '':
                    #print(id)
                    for key in sorted(points.keys()):
                        #print(key, " :: ", points[key])
                        line_points.append(self._build_point(points[key][0], points[key][1]))
                id = self._get_id(line)
                points = {}
            if len(line) > 0 and line[0].isdigit():
                if len(line_points) > 1:
                    # We get thrird lan further point from the file
                    point = self._get_point_by_distance(line, line_points[len(line_points)-1])
                else:
                    # We get the first or second point from the file
                    point = self._get_point_by_id(line)
                points.update(point)
        for key in sorted(points.keys()):
            line_points.append(self._build_point(points[key][0], points[key][1]))
        return QgsGeometry.fromPolylineXY(line_points)

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

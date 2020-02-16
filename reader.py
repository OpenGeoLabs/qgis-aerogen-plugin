import os
import math

from qgis.core import QgsGeometry, QgsLineString, QgsPointXY, QgsPoint, \
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject

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
                        self._hsl = line_value(line, cast_fn=float) * (math.pi / 180) # rad
                    if line.endswith('spacing SL'):
                        self._ssl = line_value(line, cast_fn=float)
                    if line.endswith('HTL'):
                        self._htl = line_value(line, cast_fn=float) * (math.pi / 180) # rad
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
        return [self._get_lines('sl')]

    def tl(self):
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

    def _get_azimuth_diff(self, pt1, pt2, pt3):
        """Returns difference between azimuths of two lines (pt1-pt2 and pt2-pt3)"""
        first_segment_azimuth = pt1.azimuth(pt2)
        if first_segment_azimuth < 0:
            first_segment_azimuth += 360
        second_segment_azimuth = pt2.azimuth(pt3)
        if second_segment_azimuth < 0:
            second_segment_azimuth += 360
        diff = first_segment_azimuth - second_segment_azimuth
        return diff

    def _convert_to_crs(self, line_points):
        """Converts line_points into UTM"""
        crs_src = QgsCoordinateReferenceSystem(4326)
        crs_dest = QgsCoordinateReferenceSystem(self.crs())
        xform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
        for i in range(len(line_points)):
            line_points[i] = xform.transform(line_points[i])
        return line_points

    def _convert_to_wgs(self, line_points):
        """Converts line_points into WGS84"""
        crs_src = QgsCoordinateReferenceSystem(self.crs())
        crs_dest = QgsCoordinateReferenceSystem(4326)
        xform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
        for i in range(len(line_points)):
            line_points[i] = xform.transform(line_points[i])
        return line_points

    def _correct_first_segment(self, line_points):
        """Switch first two points if the connection is not in good angle (close to normal).
        It usually means that we took the first line in a wrong dirrection.
        """
        diff = self._get_azimuth_diff(line_points[0], line_points[1], line_points[2])
        if (math.fabs(diff) > 70 and math.fabs(diff) < 110) \
                or (math.fabs(diff) > 250 and math.fabs(diff) < 290):
            # If the angle is about normal / 90 degrees, we do not do anything
            return line_points
        else:
            if line_points[0].distance(line_points[1]) < (line_points[2].distance(line_points[3]) / 2):
                pt0 = line_points[0]
                line_points[0] = line_points[1]
                line_points[1] = pt0
            return line_points

    def _correct_connections(self, line_points):
        """We prolong the lines in a case when the connection is not in normal angle"""
        i = 0
        previous_diff = 90
        while i < (len(line_points) - 3):
            diff = self._get_azimuth_diff(line_points[i], line_points[i+1], line_points[i+2])
            if not ((math.fabs(diff) > 85 and math.fabs(diff) < 95) or (math.fabs(diff) > 265 and math.fabs(diff) < 275)):
                # The angle is not close to normal
                if i == 0:
                    # We are at the beginning and do not have previous diff, so we read next diff
                    # TODO possible change to detect diff according to engles of the area, better results
                    previous_diff = self._get_azimuth_diff(line_points[2], line_points[3], line_points[4])
                distance_current = line_points[i].distance(line_points[i+1])
                distance_next = line_points[i+2].distance(line_points[i+3])
                line_g = QgsGeometry.fromPolylineXY([line_points[i + 1], line_points[i + 2]])
                # hack - there is a problem of intersection on Windows - two lines that does not intersect
                # have intersection result close to 0 0, but in digits of e-300
                intersection_error_limit = 0.000000000001
                if distance_current > distance_next:
                    # we go from longer to shorter line
                    line = QgsLineString(QgsPoint(line_points[i+2]), QgsPoint(line_points[i+3]))
                    line.extend(distance_current, 0)
                    # We rotate the line segment to find cross with extended line
                    # The rotation is based on diff (rotate to be along extended line)
                    # and angle of the previous normal line
                    line_g.rotate(diff + (180 - previous_diff), line_points[i + 1])
                    line = QgsGeometry.fromWkt(line.asWkt())
                    intersection = line_g.intersection(line).centroid()
                    if not intersection.isNull():
                        intersection = intersection.asPoint()
                        # hack
                        if intersection.x() > intersection_error_limit and intersection.y() > intersection_error_limit:
                            line_points[i + 2] = intersection
                else:
                    # we go from shorter to longer line
                    line = QgsLineString(QgsPoint(line_points[i]), QgsPoint(line_points[i+1]))
                    line.extend(0, distance_next)
                    line_g.rotate(diff + (180 - previous_diff), line_points[i + 2])
                    line = QgsGeometry.fromWkt(line.asWkt())
                    intersection = line_g.intersection(line).centroid()
                    if not intersection.isNull():
                        intersection = intersection.asPoint()
                        # hack
                        if intersection.x() > intersection_error_limit and intersection.y() > intersection_error_limit:
                            line_points[i + 1] = intersection
            i+=2
            previous_diff = diff

        return line_points

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
        line_points = self._convert_to_crs(line_points)
        line_points = self._correct_first_segment(line_points)
        line_points = self._correct_connections(line_points)
        line_points = self._convert_to_wgs(line_points)
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

import os
import math

from qgis.core import QgsGeometry, QgsPointXY

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
                    if line.endswith('Lon'):
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
        return self.generate_lines()

    def tl(self):
        return self.generate_lines(False)

    def _next_line(self, end_line=None):
        if 'dd' not in list(self._st_line_data.keys()):
            self._st_line_data['dd'] = self._ssl
            self._st_line_data['d'] = []
            self._st_line_data['alpha'] = []
            self._st_line_data['beta'] = []
            for idx in ((0, 3, 1), (1, 2, 0)):
                b = math.sqrt(pow(self._st_line_data['points'][idx[0]][0] -  self._st_line_data['points'][idx[1]][0], 2) + 
                              pow(self._st_line_data['points'][idx[0]][1] -  self._st_line_data['points'][idx[1]][1], 2))
                a = math.sqrt(pow(self._st_line_data['points'][idx[2]][0] - self._st_line_data['points'][idx[1]][0], 2) + 
                              pow(self._st_line_data['points'][idx[2]][1] - self._st_line_data['points'][idx[1]][1], 2))
                c = math.sqrt(pow(self._st_line_data['points'][idx[2]][0] - self._st_line_data['points'][idx[0]][0], 2) + 
                              pow(self._st_line_data['points'][idx[2]][1] - self._st_line_data['points'][idx[0]][1], 2))

                self._st_line_data['d'].append(b)
                self._st_line_data['alpha'].append(
                    math.asin((self._st_line_data['points'][idx[0]][1] - self._st_line_data['points'][idx[1]][1]) / self._st_line_data['d'][idx[0]])
                )
                self._st_line_data['beta'].append(
                    math.acos((pow(b, 2) + pow(c, 2) - pow(a, 2)) / ( 2 * b * c)) - (math.pi / 2)
                )

        dx = []
        dy = []
        dd = []
        for idx in range(0, len(self._st_line_data['d'])):
            dd.append(self._st_line_data['d'][idx] - (self._st_line_data['dd'] / math.cos(self._st_line_data['beta'][idx])))
            dx.append(dd[idx] * math.cos(self._st_line_data['alpha'][idx]))
            dy.append(dd[idx] * math.sin(self._st_line_data['alpha'][idx]))
        self._st_line_data['dd'] += self._ssl

        line = QgsGeometry.fromPolylineXY(
            [QgsPointXY(self._st_line_data['points'][3][0] + dx[0], self._st_line_data['points'][3][1] + dy[0]),
             QgsPointXY(self._st_line_data['points'][2][0] + dx[1], self._st_line_data['points'][2][1] + dy[1])]
        )

        if dd[0] < 0 or dd[1] < 0:
            if not end_line or not line.intersects(end_line):
                return None

            intersection  = line.intersection(end_line)
            line = QgsGeometry.fromPolylineXY(
                [intersection.asPoint(),
                 QgsPointXY(self._st_line_data['points'][2][0] + dx[1], self._st_line_data['points'][2][1] + dy[1])]
            )

        return line

    def _generate_next_lines(self, end_line=None):
        lines = []
        while True:
            line = self._next_line(end_line)
            if not line:
                break
            lines.append(line)

        return lines

    def generate_lines(self, sl=True):
        if not self._line_points:
            # lines not define, try to specify them from polygon vertices
            for pnt in self._polygon_points[:-1]:
                self._line_points.append(pnt)

        if len(self._line_points) != 4:
            raise AerogenReaderError("Unable to generate line geometry")

        d_p = []
        if sl:
            r = ((0, 1), (1, 2), (2, 0))
        else:
            r = ((3, 0), (2, 3), (2, 0))
        for i, j in r:
            d_p.append(math.sqrt(pow(self._line_points[i][0] - self._line_points[j][0], 2) +
                                 pow(self._line_points[i][1] - self._line_points[j][1], 2))
            )

        # cos(alpha) = (b^2 + c^2 - a^2) / (2bc)
        sl_alpha = p_alpha = math.acos((pow(d_p[0], 2) +
                                            pow(d_p[1], 2) -
                                            pow(d_p[2], 2)) /
                                           (2 * d_p[0] * d_p[1]))

        # sin(beta) = (b * sin(alpha)) / a
        p_gama = math.pi - (p_alpha + (math.asin((d_p[0] * math.sin(p_alpha)) / d_p[2])))

        if sl:
            sl_gama = (math.pi / 2 + p_gama + \
                       (math.asin((self._line_points[2][1] - self._line_points[0][1]) / d_p[2]))) - \
                       self._hsl
        else: # tl
            sl_gama = self._htl - (math.pi + \
                     (math.asin((self._line_points[0][0] - self._line_points[3][0]) / d_p[0])))

        # a = (b * sin(alpha) / sin(beta)
        d_sl = (d_p[0] * math.sin(sl_alpha)) / math.sin(math.pi - sl_alpha - sl_gama)

        if sl:
            phi = 1.5 * math.pi - self._hsl
        else:
            phi = self._htl - math.pi

        if sl:
            dx = d_sl * math.cos(phi)
            dy = d_sl * math.sin(phi)
        else:
            dx = d_sl * math.sin(phi)
            dy = d_sl * math.cos(phi)

        if sl:
            self._st_line_data = {
                'points' : [self._line_points[0],
                            QgsPointXY(self._line_points[0][0] + dx, self._line_points[0][1] + dy),
                            self._line_points[2],
                            self._line_points[3]
                ],
                'endline' : QgsGeometry.fromPolylineXY([self._line_points[2], self._line_points[3]])
            }
        else:
            self._st_line_data = {
                'points' : [self._line_points[0],
                            QgsPointXY(self._line_points[0][0] - dx, self._line_points[0][1] - dy),
                            self._line_points[2],
                            self._line_points[1],
                ],
                'endline' : QgsGeometry.fromPolylineXY([self._line_points[1], self._line_points[2]])
            }

        lines = self._generate_next_lines(self._st_line_data['endline'])
        lines.insert(0, QgsGeometry.fromPolylineXY([self._st_line_data['points'][0], self._st_line_data['points'][1]]))

        return lines

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

# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AeroGen
                                 A QGIS plugin
 AeroGen Plugin
                             -------------------
        begin                : 2017-04-24
        copyright            : (C) 2017 by CTU GeoForAll Lab
        email                : martin.landa@fsv.cvut.cz
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load AeroGen class from file AeroGen.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .aerogen import AeroGen
    return AeroGen(iface)

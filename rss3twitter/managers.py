# -*- coding: utf-8 -*- #
from datetime import datetime

from django.db.models.manager import Manager

class PublicacionTwitterManager(Manager):

    def fecha_proxima_publicacion(self):
        fecha_minima = datetime.max
        for pub in self.activos().defer('ultima_actualizacion', 'frecuencia'):
            fecha = pub.proxima_actualizacion()
            if fecha < fecha_minima:
                fecha_minima = fecha

        return fecha_minima

    def activos(self):
         return super(PublicacionTwitterManager, self).get_query_set().filter(activo=True, cuenta_twitter__activo=True, aplicacion__activo=True, feed_rss__activo=True).order_by('frecuencia')
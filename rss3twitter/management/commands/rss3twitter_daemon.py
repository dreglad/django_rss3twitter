# -*- coding: utf-8 -*- #
from daemonextension import DaemonCommand
from django.conf import settings
import time
from datetime import datetime, timedelta
from rss3twitter.models import PublicacionTwitter, FeedEntryPublicado
from django.db.models import Max, Min
import sys
import os

class Command(DaemonCommand):
    stdout = os.path.join(settings.PROJECT_PATH, "log/rss3twitter_daemon.log")
    stderr = os.path.join(settings.PROJECT_PATH, "log/rss3twitter_daemon.err")
    stderr = stdout
    pidfile = os.path.join(settings.PROJECT_PATH, "pid/rss3twitter_daemon.pid")
    umask = 022

    def handle_daemon(self, *args, **options):
        
        while (True):
            print "%s Buscando pblicaciones activas." % datetime.now()
            for publicacion in PublicacionTwitter.objects.activos():
                print(u'Para publicacion %d' % publicacion.pk)
                try:
                    num = publicacion.publicar_nuevos()
                    print "Publicados %d mensajes en Twitter para la publicacion: %s" % (num, publicacion)
                except Exception, e:
                    print "Error encontrado al publicar en Twitter: %s" % e
                    raise e

            td = PublicacionTwitter.objects.fecha_proxima_publicacion() - datetime.now()
            segundos = td.days * 24 * 60 * 60 + td.seconds

            print "Proxima publicación en %d segundos, descansando hasta entonces..." % segundos
            sys.stdout.flush()
            
            maximo_desface_maximo = PublicacionTwitter.objects.aggregate(Max('desface_maximo'))['desface_maximo__max']
            if maximo_desface_maximo < 24: maximo_desface_maximo = 24
            feps = FeedEntryPublicado.objects.filter(fecha_publicacion__lt=datetime.now() - timedelta(hours=maximo_desface_maximo))

            if feps.exists():
                count = feps.count()
                # Desactivado eliminación para eztadísticas
                #feps.delete()
                #print "Eliminados %d registros viejos de FeedEntryPublicado" % count
            else:
                print "Sin registros viejos de FeedEntryPublicado para eliminar con un maximo desface maximo %d horas" % maximo_desface_maximo
                
            time.sleep(segundos if segundos>0 else 60)
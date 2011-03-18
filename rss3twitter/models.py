# -*- coding: utf-8 -*- #
from django.db import models
from datetime import timedelta, datetime
import feedparser
from rss3twitter.oauthtwitter import OAuthApi
import rss3twitter.managers
#from django.utils.html import strip_tags
from django.utils.encoding import smart_unicode
from django.template.defaultfilters import slugify
from rss3twitter import  bitly, managers

class AplicacionTwitter(models.Model):
    nombre = models.CharField(max_length=255)
    consumer_key = models.CharField(max_length=100, help_text=u'Dato proporcionado por twitter al crear una aplicación: twitter.com/apps')
    consumer_secret = models.CharField(max_length=100, help_text=u'Dato proporcionado por twitter al crear una aplicación: twitter.com/apps')
    bitly_login = models.CharField(max_length=255, blank=True, null=True)
    bitly_api_key = models.CharField(max_length=255, blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __unicode__(self):
        return u'%s' % self.nombre

    class Meta:
        ordering = ['-id']
        verbose_name = u'Aplicació de Twitter'
        verbose_name_plural = u'Aplicaciones de Twitter'


class CuentaTwitter(models.Model):
    usuario = models.CharField(max_length=255)
    monitored = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    def __unicode__(self):
        return u'%s' % self.usuario

    class Meta:
        ordering = ['usuario']
        verbose_name = u'cuenta en Twitter'
        verbose_name_plural = u'cuentas en Twitter'

class AplicacionCuentaTwitter(models.Model):
    aplicacion = models.ForeignKey(AplicacionTwitter, verbose_name=u'aplicación en Twitter')
    cuenta_twitter = models.ForeignKey('CuentaTwitter')
    oauth_token = models.CharField(max_length=255, null=True, blank=True, editable=False)
    oauth_token_secret = models.CharField(max_length=255, null=True, blank=True, editable=False)

    def get_twitter_object(self):
        return OAuthApi(self.aplicacion.consumer_key, self.aplicacion.consumer_secret, self.oauth_token, self.oauth_token_secret)

    def __unicode__(self):
        return u'app:%s account:%s' % (self.aplicacion, self.cuenta_twitter)


class FeedRSS(models.Model):
    url = models.URLField()
    nombre = models.CharField(max_length=255, blank=True, null=True)
    activo = models.BooleanField(default=True)
    def __unicode__(self):
        return u'%s' % (self.nombre if self.nombre else self.url)

    class Meta:
        verbose_name = u'feed RSS'
        verbose_name_plural = u'Feeds RSS'

FRECUENCIA_CHOICES = (
    (60*1, u'Cada minuto'), (60*5, u'Cada 5 minutos'), (60*10, u'Cada 10 minutos'), (60*20, u'Cada 20 minutos'),
    (60*30, u'Cada 30 minutos'), (60*60, u'Cada hora'), (6300*2, u'Cada 2 horas'), (3600*5, u'Cada 5 horas'),
    (3600*10, u'Cada 10 horas'), (3600*20, u'Cada 20 horas'),
)


class FeedEntryPublicado(models.Model):
    publicacion_twitter = models.ForeignKey('PublicacionTwitter')
    contenido = models.TextField(u'contenido',  blank=True, null=True)
    link = models.URLField()
    fecha_rss = models.DateTimeField(u'fecha de feed')
    fecha_publicacion = models.DateTimeField(u'fecha de publicación', auto_now_add=True)

    class Meta:
        ordering = ('-fecha_publicacion', '-fecha_rss')
        verbose_name = u'entrada RSS publicado en Twitter'
        verbose_name_plural = u'entradas RSS publicados en Twitter'

class PublicacionTwitter(models.Model):
    cuenta_twitter = models.ForeignKey(CuentaTwitter)
    aplicacion = models.ForeignKey(AplicacionTwitter, verbose_name=u'aplicación en Twitter')
    feed_rss = models.ForeignKey(FeedRSS)
    frecuencia = models.PositiveIntegerField(choices=FRECUENCIA_CHOICES)
    desface_maximo = models.PositiveIntegerField(u'desface máximo', default=24, help_text=u'Número máximo de horas de diferencia para publicar entradas RSS. Un valor de cero o vacío se desactiva este límite')
    entradas_maximas = models.PositiveIntegerField(u'entradas máximas', default=25, help_text=u'Número máximo de entradas del RSS. Sólo se a consideran las N últimas entradas. Un valor de cero o vacío desactiva este límite')
    activo = models.BooleanField(default=True)
    prefijo = models.CharField(max_length=100, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(null=True, editable=False)

    objects = managers.PublicacionTwitterManager()

    def get_aplicacion_cuenta_twitter(self):
        app_ctas = AplicacionCuentaTwitter.objects.filter(aplicacion=self.aplicacion, cuenta_twitter=self.cuenta_twitter)[:1]
        if (app_ctas):
            return app_ctas[0]
        else:
            app_cta = AplicacionCuentaTwitter(aplicacion=self.aplicacion, cuenta_twitter=self.cuenta_twitter)
            app_cta.save()
            return app_cta


    def proxima_actualizacion(self):
        if self.ultima_actualizacion:
            return self.ultima_actualizacion + timedelta(seconds=self.frecuencia)
        else:
            return datetime.now()

    def publicar_nuevos(self):
        publicados = 0
        feed_entries = self.getFeedEntries()
        
        if self.entradas_maximas > 0:
            feed_entries = feed_entries[:self.entradas_maximas]
            feed_entries.reverse()
        
        for feed_entry in feed_entries:
            if self.nuevo(feed_entry) and (self.desface_maximo==0 or datetime(*feed_entry.updated_parsed[:6]) > datetime.now() - timedelta(hours=self.desface_maximo)):
                if self.publicar(feed_entry): publicados += 1
            
        self.ultima_actualizacion = datetime.now()
        self.save()
        
        return publicados

    def publicar(self, feed_entry):
        mensaje = self.mensaje_twitter(feed_entry)

        try:
            self.get_aplicacion_cuenta_twitter().get_twitter_object().UpdateStatus(smart_unicode(mensaje).encode('utf-8'))
            FeedEntryPublicado(publicacion_twitter=self, link=feed_entry.link, contenido=mensaje, fecha_rss=datetime(*feed_entry.updated_parsed[:6])).save()
            self.ultima_actualizacion = datetime.now()
            self.save()
            return True
        except Exception, e:
            FeedEntryPublicado(publicacion_twitter=self, contenido=u'Error: %s' % e, fecha_rss=datetime(*feed_entry.updated_parsed[:6])).save()
            return False

    def mensaje_twitter(self, feed_entry):
        """Devuelve cadena con el mensaje para twitter"""
        prefijo = u''
        hashtags = u''
        link = u''
        mensaje = u''

        # Prefijo opcional
        prefijo = u'%s ' % self.prefijo.strip() if self.prefijo else u''

        # Hashtags para twitter, pueden venir
        # del tag tags (jornada) o ttl (multimedia teleSUR)
        if 'tags' in feed_entry:
            for tag in feed_entry['tags']:
                hashtags+= u'#%s ' % slugify(tag.term.strip()).replace('-', '')
            hashtags = hashtags.strip()

        if 'ttl' in feed_entry and feed_entry['ttl'].strip(): # ttl --> hack para mandar hashtags en RSS de multimedia
            hashtags+= feed_entry['ttl'].strip()

        # Link, intentar conseguirlo a través de Bitly PRO.
        try:
            if not self.aplicacion.bitly_login and not self.aplicacion.bitly_api_key:
                raise Exception # Lanzar excepción si no se puede conectar a Bitly
            api = bitly.Api(login=self.aplicacion.bitly_login, apikey=self.aplicacion.bitly_api_key)
            link = u'%s ' % api.shorten(feed_entry.link)
            link_len = len(link)
        except:
            # Si no se pudo conectar a bitly dar por hecho que twitter acorará la URL con bit.ly
            link = u'%s ' % feed_entry.link
            link_len = 20 + 1 # default bit.ly

        # Detemrina el cuerpo mensaje calculando número de caracteres que nos quedan para el mensaje
        maximo = 140 - len(prefijo) - len(hashtags) - link_len
        if len(feed_entry.title) > maximo:
            mensaje = u'%s... ' % feed_entry.title.strip()[:maximo-3]
        else:
            mensaje = u'%s ' % feed_entry.title.strip()

        # COnstruye y devuelve el mensaje
        return u'%s%s%s%s' % (prefijo, mensaje, link, hashtags)


    def getFeedEntries(self):
        """Realiza parse y Devuelve diccionario con las entradas actuales del feed"""
        return feedparser.parse(self.feed_rss.url).entries

    def nuevo(self, feed_entry):
        """Devuelve False si ya existe registro de  entrada publicada """
        return not FeedEntryPublicado.objects.filter(publicacion_twitter=self, link=feed_entry.link, fecha_rss=datetime(*feed_entry.updated_parsed[:6])).exists()

    def __unicode__(self):
        return u'%s hacia usuario %s vía aplicación %s' % (self.feed_rss, self.cuenta_twitter, self.aplicacion)

    class Meta:
        verbose_name = u'publicación en Twitter'
        verbose_name_plural = u'publicaciones en Twitter'

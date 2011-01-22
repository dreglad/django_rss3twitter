# -*- coding: utf-8 -*- #
from django.contrib import admin
from rss3twitter.models import *
from rss3twitter.oauthtwitter import OAuthApi
from django.conf.urls.defaults import patterns
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
import marshal

class CuentaTwitterAdmin(admin.ModelAdmin):

    list_display = ('usuario', 'activo')
    search_fields = ['usuario']
    list_per_page = 20

class AplicacionTwitterAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'consumer_key', 'consumer_secret', 'bitly_login', 'bitly_api_key')
    list_per_page = 20

class FeedRSSAdmin(admin.ModelAdmin):
    list_display = ('url', 'nombre', 'activo')
    search_fields = ['url', 'nombre']
    list_per_page = 20

    
def autorizar_twitter_view(request):
    app_cta = get_object_or_404(AplicacionCuentaTwitter, pk=request.GET.get('pk'))

    twitter = OAuthApi(app_cta.aplicacion.consumer_key, app_cta.aplicacion.consumer_secret)
    access_token = twitter.getAccessToken(marshal.loads(app_cta.oauth_token_secret), request.GET.get('pin'))

    app_cta.oauth_token = access_token['oauth_token']
    app_cta.oauth_token_secret = access_token['oauth_token_secret']
    app_cta.save()

    return HttpResponse()
    
class PublicacionTwitterAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'cuenta_twitter', 'aplicacion', 'feed_rss', 'prefijo', 'frecuencia', 'limites', 'ultima_actualizacion', '_autorizacion',  'activo')
    actions = ['publicar_nuevos', 'desautorizar']
    ordering = ('cuenta_twitter',)
    list_per_page = 20

    def desautorizar(modeladmin, request, queryset):
        for ct in queryset:
            app_cta = ct.get_aplicacion_cuenta_twitter()
            app_cta.oauth_token = None
            app_cta.oauth_token_secret = None
            app_cta.save()
    desautorizar.short_description = u'Desautorizar cuenta de twitter'

    def limites(self, obj):
        return u'%d entradas / %d horas' % (int(obj.entradas_maximas), int(obj.desface_maximo)) 

    def _autorizacion(self, obj):
        app_cta = obj.get_aplicacion_cuenta_twitter()
        if not app_cta.oauth_token:
            try:
                twitter = OAuthApi(obj.aplicacion.consumer_key, obj.aplicacion.consumer_secret)

                if not app_cta.oauth_token_secret:
                    temp_credentials = twitter.getRequestToken()
                    app_cta.oauth_token_secret = marshal.dumps(temp_credentials, 0)
                else:
                    temp_credentials = marshal.loads(app_cta.oauth_token_secret)
                    
                url = twitter.getAuthorizationURL(temp_credentials)

                app_cta.save()
                return u'<a target="_blank" href="%s">Link de autorización</a><br />Código: <input type="text" id="pin%d" /> <input type="button" onclick=\'django.jQuery.get("autorizar", {pk: "%d", pin: django.jQuery("#pin%s").val() }, function(data){history.go(0);} );\' value="Autorizar" />' % (url, app_cta.pk, app_cta.pk, app_cta.pk)
            except Exception, e:
                return u'Error al generar link para autorización. Verificar llaves de acceso a la aplicación en Twitter (consumer_key, consumer_secret): %s' % e
        else:
            try:
                twitter = app_cta.get_twitter_object()
                return u'Cuenta autorizada'
            except Exception, e:
                return u'Error al obtener permiso de acceso a la cuenta: %s' % e
    _autorizacion.allow_tags = True
    _autorizacion.verbose_name = u'autorización'

    def get_urls(self):
        urls = super(PublicacionTwitterAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^autorizar/$', autorizar_twitter_view)
        )
        return my_urls + urls

    def publicar_nuevos(self, request, queryset):
        num = 0
        for publicacion in queryset:
            num += publicacion.publicar_nuevos()
        self.message_user(request, "Se publicaron %d entradas a Twitter" % num)
    publicar_nuevos.short_description = u'Publicar ahora nuevas entradas de RSS en Twitter'

class FeedEntryPublicadoAdmin(admin.ModelAdmin):
    list_display = ('pk', 'fecha_publicacion', 'fecha_rss', 'publicacion_twitter', 'contenido', 'link')
    list_per_page = 30
    date_hierachy = 'fecha_publicacion'
    list_filter = ('fecha_publicacion', 'fecha_rss', 'publicacion_twitter')

admin.site.register(CuentaTwitter, CuentaTwitterAdmin)
admin.site.register(FeedEntryPublicado, FeedEntryPublicadoAdmin)
admin.site.register(FeedRSS, FeedRSSAdmin)
admin.site.register(PublicacionTwitter, PublicacionTwitterAdmin)
admin.site.register(AplicacionTwitter, AplicacionTwitterAdmin)


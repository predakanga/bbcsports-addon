#!/usr/bin/env python
# -*- coding:Utf-8 -*-


#
# Modules
#

import cookielib
import random
import xbmc, xbmcgui, xbmcaddon
import utils

__scriptname__  = 'BBCSport'
__scriptid__ = "plugin.video.bbcsport"
__addoninfo__ = utils.get_addoninfo(__scriptid__)
__addon__ = __addoninfo__["addon"]
__settings__   = xbmcaddon.Addon(id=__scriptid__)




class Navigator:
	
	timeOut   = 60
	listeUserAgents = [ 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_5; fr-fr) AppleWebKit/525.18 (KHTML, like Gecko) Version/3.1.2 Safari/525.20.1',
						'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/14.0.835.186 Safari/535.1',
						'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/525.13 (KHTML, like Gecko) Chrome/0.2.149.27 Safari/525.13',
						'Mozilla/5.0 (X11; U; Linux x86_64; en-us) AppleWebKit/528.5+ (KHTML, like Gecko, Safari/528.5+) midori',
						'Mozilla/5.0 (Windows NT 6.0) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/13.0.782.107 Safari/535.1',
						'Mozilla/5.0 (Macintosh; U; PPC Mac OS X; en-us) AppleWebKit/312.1 (KHTML, like Gecko) Safari/312',
						'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11',
						'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.8 (KHTML, like Gecko) Chrome/17.0.940.0 Safari/535.8' ]
	
	def __init__( self, proxy = None ):
		import socks
		import socket
		socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "dlake-radio.lake.to", 1081)
		socket.socket = socks.socksocket
		import urllib2
		self.proxy = proxy
		
		# Cookiejar + urlopener
		self.cookiejar            = cookielib.CookieJar()
		if( proxy is None ):
			self.urlOpener        = urllib2.build_opener( urllib2.HTTPCookieProcessor( self.cookiejar ) )
		else:
			self.urlOpener        = urllib2.build_opener( urllib2.HTTPCookieProcessor( self.cookiejar ), urllib2.ProxyHandler( { 'http' : self.proxy } ) )
		# Spoof user-agent
		self.urlOpener.addheaders = [ ( 'User-agent', random.choice( self.listeUserAgents ) ) ]		

	def getFile( self, url ):
		import socks
		import socket
		if __settings__.getSetting('proxy_use') == 'true':
			(proxy_type, proxy_server, proxy_port, proxy_dns, proxy_user, proxy_pass) = self.get_proxy()
		#socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "dlake-radio.lake.to", 1081)
			socks.setdefaultproxy(proxy_type, proxy_server, proxy_port, proxy_dns, proxy_user, proxy_pass)
			socket.socket = socks.socksocket
		import urllib2
		try:
			request = urllib2.Request( url )
			page    = self.urlOpener.open( request, timeout = self.timeOut )
			data = page.read()
			return data
		except urllib2.URLError, e :
			if( hasattr( e, 'reason' ) ):
				print "Error" + ( e.reason )
			elif( hasattr( e, 'code' ) ):
				print  "Error %d" %( e.code )
			raise

	def get_proxy(self):
		import socks
		proxy_server = None
		proxy_type_id = 0
		proxy_port = 8080
		proxy_user = None
		proxy_pass = None
		try:
			proxy_server = __settings__.getSetting('proxy_server')
			proxy_type_id = __settings__.getSetting('proxy_type')
			proxy_port = int(__settings__.getSetting('proxy_port'))
			proxy_user = __settings__.getSetting('proxy_user')
			proxy_pass = __settings__.getSetting('proxy_pass')
		except:
			pass

		if   proxy_type_id == '0': proxy_type = socks.PROXY_TYPE_HTTP_NO_TUNNEL
		elif proxy_type_id == '1': proxy_type = socks.PROXY_TYPE_HTTP
		elif proxy_type_id == '2': proxy_type = socks.PROXY_TYPE_SOCKS4
		elif proxy_type_id == '3': proxy_type = socks.PROXY_TYPE_SOCKS5

		proxy_dns = True
    
		return (proxy_type, proxy_server, proxy_port, proxy_dns, proxy_user, proxy_pass)

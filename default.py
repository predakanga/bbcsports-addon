import urllib,urllib2, re,sys,socket,os,md5,datetime,xbmcplugin,xbmcgui, xbmcaddon, threading
import os, os.path
import thread

# external libs
sys.path.insert(0, os.path.join(os.getcwd(), 'lib'))
import utils, Navigator, socks, logging, time, httplib2, httplib

from BeautifulSoup import BeautifulSoup
from BBCDL import BBCDL

finalPart = True
#import BeautifulStoneSoup

# setup cache dir
__scriptname__  = 'BBCSport'
__scriptid__ = "plugin.video.bbcsport"
__addoninfo__ = utils.get_addoninfo(__scriptid__)
__addon__ = __addoninfo__["addon"]
__settings__   = xbmcaddon.Addon(id=__scriptid__)



DIR_USERDATA   = xbmc.translatePath(__addoninfo__["profile"])
SUBTITLES_DIR  = os.path.join(DIR_USERDATA, 'Subtitles')
IMAGE_DIR      = os.path.join(DIR_USERDATA, 'Images')
thumb_dir = os.path.join(__addoninfo__['path'], 'resources', 'media')


if not os.path.isdir(DIR_USERDATA):
    os.makedirs(DIR_USERDATA)
if not os.path.isdir(SUBTITLES_DIR):
    os.makedirs(SUBTITLES_DIR)
if not os.path.isdir(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)


def get_proxy():
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

def get_httplib():
    http = None
    try:
        if __settings__.getSetting('proxy_use') == 'true':
            (proxy_type, proxy_server, proxy_port, proxy_dns, proxy_user, proxy_pass) = get_proxy()
            logging.info("Using proxy: type %i rdns: %i server: %s port: %s user: %s pass: %s", proxy_type, proxy_dns, proxy_server, proxy_port, "***", "***")
            http = httplib2.Http(proxy_info = httplib2.ProxyInfo(proxy_type, proxy_server, proxy_port, proxy_dns, proxy_user, proxy_pass))
        else:
 	  logging.info("No Proxy\n")
          http = httplib2.Http()
    except:
        raise
        logging.error('Failed to initialize httplib2 module')

    return http

http = get_httplib()


       
# what OS?        
environment = os.environ.get( "OS", "xbox" )


############## SUBS #################

def chomps(s):
    return s.rstrip('\n')

def httpget(url):
	resp = ''
	data = ''
	http = get_httplib()
	resp, data = http.request(url, "GET")
	return data


def download_subtitles(url, offset):
		# Download and Convert the TTAF format to srt
		# SRT:
		#1
		#00:01:22,490 --> 00:01:26,494
		#Next round!
		#
		#2
		#00:01:33,710 --> 00:01:37,714
		#Now that we've moved to paradise, there's nothing to eat.
		#
    
		# TT:
		#<p begin="0:01:12.400" end="0:01:13.880">Thinking.</p>
    
	logging.info('subtitles at =%s' % url)
	outfile = os.path.join(SUBTITLES_DIR, 'itv.srt')
	fw = open(outfile, 'w')
    
	if not url:
		fw.write("1\n0:00:00,001 --> 0:01:00,001\nNo subtitles available\n\n")
		fw.close() 
		return outfile
	txt = httpget(url)
	try:
		txt = txt.decode("utf-16")
	except UnicodeDecodeError:
		txt = txt[:-1].decode("utf-16")
	txt = txt.encode('latin-1')
	p= re.compile('^\s*<p.*?begin=\"(.*?)\.([0-9]+)\"\s+.*?end=\"(.*?)\.([0-9]+)\"\s*>(.*?)</p>')
	i=0
	prev = None

		# some of the subtitles are a bit rubbish in particular for live tv
		# with lots of needless repeats. The follow code will collapse sequences
		# of repeated subtitles into a single subtitles that covers the total time
		# period. The downside of this is that it would mess up in the rare case
		# where a subtitle actually needs to be repeated 
	entry = None
	for line in txt.splitlines():
		subtitles1 = re.findall('<p.*?begin="(...........)" end="(...........)".*?">(.*?)</p>',line)
		if subtitles1:
			for start_time, end_time, text in subtitles1:
				r = re.compile('<[^>]*>')
				text = r.sub('',text)
				start_hours = re.findall('(..):..:..:..',start_time)
				start_mins = re.findall('..:(..):..:..', start_time)
				start_secs = re.findall('..:..:(..):..', start_time)
				start_msecs = re.findall('..:..:..:(..)',start_time)
#				start_mil = start_msecs +'0'
				end_hours = re.findall('(..):..:..:..',end_time)
				end_mins = re.findall('..:(..):..:..', end_time)
				end_secs = re.findall('..:..:(..):..', end_time)
				end_msecs = re.findall('..:..:..:(..)',end_time)
#				end_mil = end_msecs +'0'
				entry = "%d\n%s:%s:%s,%s --> %s:%s:%s,%s\n%s\n\n" % (i, start_hours[0], start_mins[0], start_secs[0], start_msecs[0], end_hours[0], end_mins[0], end_secs[0], end_msecs[0], text)
				i=i+1
				print "ENTRY" + entry
		if entry: 
			fw.write(entry)
    
	fw.close()    
	return outfile

def CATS():
	video_string = "40"
	try:
		video_stream = __settings__.getSetting('video_stream')
	except:
		pass
	print "VIDEO STREAM"
	print video_stream
	if (video_stream == "0"):
		video_string = "40"
	if (video_stream == "1"):
		video_string = "50"
	if (video_stream == "2"):
		video_string = "60"
	if (video_stream == "3"):
		video_string = "70"
	if (video_stream == "4"):
		video_string = "80"
	print video_string
	addDir("BBC Olympics Channel 1","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_01/uk_sport_stream_01_" + video_string + ".f4m",3,thumb_dir + '/channel_1.png')
	addDir("BBC Olympics Channel 2","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_02/uk_sport_stream_02_" + video_string + ".f4m",3,thumb_dir + '/channel_2.png')
	addDir("BBC Olympics Channel 3","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_03/uk_sport_stream_03_" + video_string + ".f4m",3,thumb_dir + '/channel_3.png')
	addDir("BBC Olympics Channel 4","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_04/uk_sport_stream_04_" + video_string + ".f4m",3,thumb_dir + '/channel_4.png')
	addDir("BBC Olympics Channel 5","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_05/uk_sport_stream_05_" + video_string + ".f4m",3,thumb_dir + '/channel_5.png')
	addDir("BBC Olympics Channel 6","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_06/uk_sport_stream_06_" + video_string + ".f4m",3,thumb_dir + '/channel_6.png')
	addDir("BBC Olympics Channel 7","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_07/uk_sport_stream_07_" + video_string + ".f4m",3,thumb_dir + '/channel_7.png')
	addDir("BBC Olympics Channel 8","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_08/uk_sport_stream_08_" + video_string + ".f4m",3,thumb_dir + '/channel_8.png')
	addDir("BBC Olympics Channel 9","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_09/uk_sport_stream_09_" + video_string + ".f4m",3,thumb_dir + '/channel_9.png')
	addDir("BBC Olympics Channel 10","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_10/uk_sport_stream_10_" + video_string + ".f4m",3,thumb_dir + '/channel_10.png')
	addDir("BBC Olympics Channel 11","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_11/uk_sport_stream_11_" + video_string + ".f4m",3,thumb_dir + '/channel_11.png')
	addDir("BBC Olympics Channel 12","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_12/uk_sport_stream_12_" + video_string + ".f4m",3,thumb_dir + '/channel_12.png')
	addDir("BBC Olympics Channel 13","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_13/uk_sport_stream_13_" + video_string + ".f4m",3,thumb_dir + '/channel_13.png')
	addDir("BBC Olympics Channel 14","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_14/uk_sport_stream_14_" + video_string + ".f4m",3,thumb_dir + '/channel_14.png')
	addDir("BBC Olympics Channel 15","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_15/uk_sport_stream_15_" + video_string + ".f4m",3,thumb_dir + '/channel_15.png')
	addDir("BBC Olympics Channel 16","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_16/uk_sport_stream_16_" + video_string + ".f4m",3,thumb_dir + '/channel_16.png')
	addDir("BBC Olympics Channel 17","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_17/uk_sport_stream_17_" + video_string + ".f4m",3,thumb_dir + '/channel_17.png')
	addDir("BBC Olympics Channel 18","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_18/uk_sport_stream_18_" + video_string + ".f4m",3,thumb_dir + '/channel_18.png')
	addDir("BBC Olympics Channel 19","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_19/uk_sport_stream_19_" + video_string + ".f4m",3,thumb_dir + '/channel_19.png')
	addDir("BBC Olympics Channel 20","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_20/uk_sport_stream_20_" + video_string + ".f4m",3,thumb_dir + '/channel_20.png')
	addDir("BBC Olympics Channel 21","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_21/uk_sport_stream_21_" + video_string + ".f4m",3,thumb_dir + '/channel_21.png')
	addDir("BBC Olympics Channel 22","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_22/uk_sport_stream_22_" + video_string + ".f4m",3,thumb_dir + '/channel_22.png')
	addDir("BBC Olympics Channel 23","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_23/uk_sport_stream_23_" + video_string + ".f4m",3,thumb_dir + '/channel_23.png')
	addDir("BBC Olympics Channel 24","http://bbcfmhds.vo.llnwd.net/hds-live/livepkgr/_definst_/uk_sport_stream_24/uk_sport_stream_24_" + video_string + ".f4m",3,thumb_dir + '/channel_24.png')


def STREAMS():
        streams=[]
        key = get_url('http://www.itv.com/_app/dynamic/AsxHandler.ashx?getkey=please')
        for channel in range(1,5):
                streaminfo = get_url('http://www.itv.com/_app/dynamic/AsxHandler.ashx?key='+key+'&simid=sim'+str(channel)+'&itvsite=ITV&itvarea=SIMULCAST.SIM'+str(channel)+'&pageid=4567756521')
                stream=re.compile('<TITLE>(.+?)</TITLE><REF href="(.+?)" />').findall(streaminfo)
                streams.append(stream[1])
        for name,url in streams:
                addLink(name,url)

def BESTOF(url):
        response = get_url(url).replace('&amp;','&')
        match=re.compile('<li><a href="(.+?)"><img src=".+?" alt=".+?"></a><h4><a href=".+?">(.+?)</a></h4>').findall(response)
        for url,name in match:
                addDir(name,url,5,'')
                
def BESTOFEPS(url):
        response = get_url(url).replace('&amp;','&')
        eps=re.compile('<a [^>]*?title="Play" href=".+?vodcrid=crid://itv.com/(.+?)&DF=0"><img\s* src="(.*?)" alt="(.*?)"').findall(response)
        if eps:
            for url,thumb,name in eps:
                addDir(name,url,3,'http://itv.com/'+thumb,isFolder=False)
            return
        eps=re.compile('<a [^>]*?title="Play" href=".+?vodcrid=crid://itv.com/(.+?)&DF=0">(.+?)</a>').findall(response)
        if not eps: eps=re.compile('href=".+?vodcrid=crid://itv.com/(.+?)&G=.+?&DF=0">(.+?)</a>').findall(response)
        if not eps:
                eps=re.compile('<meta name="videoVodCrid" content="crid://itv.com/(.+?)">').findall(response)
                name=re.compile('<meta name="videoMetadata" content="(.+?)">').findall(response)
                eps=[(eps[0],name[0])]
        for url,name in eps:
                addDir(name,url,3,'',isFolder=False)
        
def TOP10(url):
	response = get_url(url).replace('&amp;','&')
	match = re.split('<Top10CatchUps>',response)
	match2 = re.findall('<VideoID>(.*)</VideoID>\s*.*\s*.*\s*.*\s*.*<ProgrammeName>(.*)</ProgrammeName>\s*.*\s*.*\s*<EpisodeTitle>(.*)</EpisodeTitle>\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*.*\s*<ItemMediaUrl>(.*)</ItemMediaUrl>',match[1])
	for url, name, name2, thumb in match2:
		addDir(name+' - '+name2,url,3,thumb)
	#print match[1]
	
def SHOWS(url):
        response = get_url(url)
        code=re.sub('&amp;','&',response)
        match=re.compile('<ProgrammeId>(.+?)</ProgrammeId>\r\n      <ProgrammeTitle>(.+?)</ProgrammeTitle>\r\n      <ProgrammeMediaId>.+?</ProgrammeMediaId>\r\n      <ProgrammeMediaUrl>(.+?)</ProgrammeMediaUrl>\r\n      <LastUpdated>.+?</LastUpdated>\r\n      <Url>.+?</Url>\r\n      <EpisodeCount>(.+?)</EpisodeCount>').findall(code)
        for url,name,thumb,epnumb in match:
                if not int(epnumb)<1:
                        addDir(name+' - '+epnumb+' Episodes Available.',url,2,thumb)

def EPS(url):
        response = get_url("http://www.itv.com/_app/Dynamic/CatchUpData.ashx?ViewType=1&Filter=%s&moduleID=115107"%url)
#        print response
        soup = BeautifulSoup(response,convertEntities="html")
        for episode in soup.findAll('div', attrs={'class' : re.compile('^listItem')}):
            thumb = str(episode.div.a.img['src'])
            pid = re.findall('.+?Filter=(.+?)$', str(episode.div.a['href']))[0]
	    image_name = pid + '.jpg'
	    outfile = os.path.join(IMAGE_DIR, image_name)
	    fw = open(outfile, 'wb')
	    txt = httpget(thumb)
	    fw.write(txt)
	    fw.close()
            name = str(episode.div.a.img['alt'])
            date = decode_date(str(episode.find('div', 'content').p.contents[0]))
            desc = str(episode.find('p', 'progDesc').contents[0])
            addDir(name+' '+date+'. '+desc ,pid,3,thumb,desc,isFolder=False)
        xbmcplugin.setContent(handle=int(sys.argv[1]), content='episodes')

def VIDEO(url):
	print "URL: " + url
	listitem = xbmcgui.ListItem("Olympics")
	#image_name = pid + '.jpg'
	#thumbfile = os.path.join(IMAGE_DIR, image_name)
	#listitem.setThumbnailImage(thumbfile)
	#listitem.setInfo('video', {'Title': title2[0]})
	proxy = get_proxy()
	if proxy[0] == socks.PROXY_TYPE_HTTP_NO_TUNNEL:
		proxy = None
	downloader = BBCDL(url,proxy)
	dlThread = threading.Thread(target=downloader.run)
	dlThread.start()
	progress = xbmcgui.DialogProgress()
	progress.create('Starting Stream')
	mplayer = MyPlayer()
	try:
		filename = __settings__.getSetting('download_folder') + "bbcsports.flv"
	except:
		exit (-1)
	if os.name == 'nt':
		filename = '\\\\.\\pipe\\bbcsports.flv'
	# Wait for stream to begin
	while not downloader.dataWritten:
		print "Waiting for data to be written"
		time.sleep(1)
	# Wait a second to let the data actually be written - we have to set the flag before
	# the data is really written, as FIFO writes are blocking
	time.sleep(1)
	# It hath begun!
	progress.close()
	mplayer.play(filename,listitem)
	time.sleep(10)
	# Wait till it finishes playing, and kill the thread
	while xbmc.Player().isPlaying():
		time.sleep(10)
	print "Finished playing"
	downloader.dataThreadKill = True
	#while xbmc.Player().isPlaying():
	#	print "Playing"
	#	xbmc.sleep(100)
	#os.remove(lockfile)
	return

class MyPlayer (xbmc.Player):
     def __init__ (self):
        xbmc.Player.__init__(self)

        
     def play(self, url, listitem):
        print 'Now im playing... %s' % url

        xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER).play(url, listitem)
        



############## End MyPlayer Class ###############



def decode_redirect(url):
	
    # some of the the urls passed in are redirects that are not handled by XBMC.
    # These are text files with multiple stream urls

    #if environment in ['xbox', 'linux']:
    #    # xbox xbmc works just fine with redirects
    #    return url

    response = get_url(url).replace('&amp;','&')
    match=re.compile('Ref1\=(http.*)\s').findall(response)

    stream_url = None
    if match:
        stream_url = match[0].rstrip()
    else:
        # no match so pass url to xbmc and see if the url is directly supported 
        stream_url = url

    return stream_url

def decode_date(date):
    # format eg Sat 10 Jan 2009
    (dayname,day,monthname,year) = date.split(' ')
    if not year:
        return date
    month=1
    monthname = monthname.lower()
    lookup = {'jan':1, 'feb':2, 'mar':3, 'apr':4, 'may':5, 'jun':6, 'jul':7, 'aug':8, 'sep':9, 'oct':10, 'nov':11, 'dec':12}
    if lookup.has_key(monthname[:3]):
        month=lookup[monthname[:3]]
    
    try:
        # yes I know the colons are weird but the 2009-01-25 xbox release
        # when in filemode (but not library mode) converts YYYY-MM-DD in (YYYY)
        sep='-'
        if environment == 'xbox': sep=':' 
        ndate = "%04d%s%02d%s%02d" % (int(year),sep,int(month),sep,int(day))
    except:
        # oops funny date, return orgional date
        return date
    #print "Date %s from %s" % (ndate, date)
    return ndate

def get_url(url):
    #try:
        #req = urllib2.Request(url)
        #req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.1.14) Gecko/20080404 Firefox/2.0.0.14')
        #return urllib2.urlopen(req).read()
    
    # first try
    http = get_httplib()
    data = None    
    try:
        resp, data = http.request(url, 'GET')
    except: pass
    
    # second try
    if not data:
        try:
            resp, data = http.request(url, 'GET')
        except: 
            dialog = xbmcgui.Dialog()
            dialog.ok('Network Error', 'Failed to fetch URL', url)
            print 'Network Error. Failed to fetch URL %s' % url
            raise
    
    return data


def get_params():
        param=[]
        paramstring=sys.argv[2]
        if len(paramstring)>=2:
                params=sys.argv[2]
                cleanedparams=params.replace('?','')
                if (params[len(params)-1]=='/'):
                        params=params[0:len(params)-2]
                pairsofparams=cleanedparams.split('&')
                param={}
                for i in range(len(pairsofparams)):
                        splitparams={}
                        splitparams=pairsofparams[i].split('=')
                        if (len(splitparams))==2:
                                param[splitparams[0]]=splitparams[1]
                                
        return param

      
def addLink(name,url):
        ok=True
        thumbnail_url = url.split( "thumbnailUrl=" )[ -1 ]
        liz=xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=thumbnail_url)
        liz.setInfo( type="Video", infoLabels={ "Title": name } )
        ok=xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=url,listitem=liz)
        return ok

def addDir(name,url,mode,iconimage,plot='',isFolder=True):
        u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)
        ok=True
        #print "addDir " + name
        liz=xbmcgui.ListItem(name,iconImage="DefaultVideo.png", thumbnailImage=iconimage)
        liz.setInfo( type="Video", infoLabels={ "Title": name, "Plot": plot} )
        ok=xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=u,listitem=liz,isFolder=False)
        return ok




params=get_params()
url=None
name=None
mode=None
try:
        url=urllib.unquote_plus(params["url"])
except:
        pass
try:
        name=urllib.unquote_plus(params["name"])
except:
        pass
try:
        mode=int(params["mode"])
except:
        pass
print "Mode: "+str(mode)
print "URL: "+str(url)
print "Name: "+str(name)

if mode==None or url==None or len(url)<1:
	print "categories"
	CATS()
elif mode==1:
	print "index of : "+url
	SHOWS(url)
elif mode==2:
	print "Getting Episodes: "+url
	EPS(url)
elif mode==3:
	print "Getting Videofiles: "+url
	VIDEO(url)
elif mode==4:
	print "Getting Videofiles: "+url
	BESTOF(url)
elif mode==5:
	print "Getting Videofiles: "+url
	BESTOFEPS(url)
elif mode==6:
	print "Getting Videofiles: "+url
	STREAMS()
elif mode==7:
	print "Top 10: " +url
	TOP10(url)



xbmcplugin.endOfDirectory(int(sys.argv[1]))

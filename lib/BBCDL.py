#!/usr/bin/env python
# -*- coding:Utf-8 -*-


import base64
import binascii
import os
import os.path
import re
import sys
import urllib2
import xml.etree.ElementTree
import xml.sax
import struct
import string
import time
import xbmc, xbmcplugin, xbmcgui, xbmcaddon, utils
import datetime
import pycurl
import Queue
import threading
import random
import socks

from Navigator import Navigator

__scriptname__  = 'BBCSport'
__scriptid__ = "plugin.video.bbcsport"
__addoninfo__ = utils.get_addoninfo(__scriptid__)
__addon__ = __addoninfo__["addon"]
__settings__   = xbmcaddon.Addon(id=__scriptid__)
DIR_USERDATA   = xbmc.translatePath(__addoninfo__["profile"])

class CurlData(object):
	def __init__(self):
		self.contents = ''
	
	def body_callback(self, buf):
		self.contents = self.contents + buf

	def reset(self):
		self.contents = ''

class BBCDL( object ):
	
	def __init__( self, url, proxy = None):
		try:
			self.outputfile = __settings__.getSetting('download_folder') + "/bbcsports.flv"
		except:
			print "Output Filename must be set"
			exit (-1)
		self.pipeHandle = None
		if os.name == 'nt':
			self.outputfile = '\\\\.\\pipe\\bbcsports.flv'
			# Create the named pipe
			import win32file, win32pipe
			self.pipeHandle = win32pipe.CreateNamedPipe(self.outputfile, win32pipe.PIPE_ACCESS_DUPLEX, win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT, 50, 4096, 4096, 10000, None)
			if self.pipeHandle == win32file.INVALID_HANDLE_VALUE:
				print "Fatal: Couldn't create named pipe. Exiting."
				exit (-1)
		else:
			# Create the FIFO
			if os.path.exists(self.outputfile):
				os.unlink(self.outputfile)
			os.mkfifo(self.outputfile)
			
		self.url              = url
		self.proxy            = proxy
		self.navigator        = Navigator( self.proxy )
		
		self.manifestURL      = None
		self.drm              = None
		self.segNum           = 1
		self.pos              = 0
		self.boxType          = None
		self.boxSize          = None
		self.fragNum          = None
		self.rename           = False
		self.prevTagSize      = 4
		self.tagHeaderLen     = 11
		self.baseTS           = False
		self.prevAudioTS      = -1
		self.prevVideoTS      = -1
		self.TIMECODE_DURATION = 8
		self.duration          = 0
		self.audio             = False
		self.video             = False
		self.prevAVC_Header    = False
		self.prevAAC_Header    = False
		self.AVC_HeaderWritten = False
		self.AAC_HeaderWritten = False
		self.dataQueue         = Queue.Queue(50)
		self.dataThread        = None
		self.dataThreadKill    = False
		self.dataWritten       = False
		self.needNewBootstrap  = False
		self.flvHeader = bytearray.fromhex(unicode('464c5601050000000900000000'))
		self.flvHeaderLen = len(self.flvHeader)



	def run(self):
		print "Started download thread"
		flv = None

		self.baseUrl = self.url[0: self.url.rfind("/")]
		# Get the manifest
		self.manifest = self.navigator.getFile(self.url)
		# Parse the manifest
		self.parseManifest()
		segNum = self.segNum
		fragNum = self.fragNum
		#print segNum
		#print fragNum
		#print self.fragCount

		self.baseFilename = (self.streamid.attrib["streamId"] + "Seg%d" + "-Frag") % (segNum)
		self.fragUrl = self.baseUrl + "/" + self.streamid.attrib["url"]

		# Kick off the data fetching thread
		self.dataThread = threading.Thread(target=self.runDataThread)
		self.dataThread.start()	

		while not self.dataThreadKill:
			fragNum, data = self.dataQueue.get()

			if fragNum is None:
				# New bootstrap info for us
				sys.stdout.write("Updating bootstrap info")
				self.UpdateBootstrapInfoWithData(data)
			else:
				sys.stdout.write("Decoding fragment %d of %d\r" % (fragNum, self.fragCount))
				# Create the FLV if it doesn't exist
				if (flv is None):
					self.start = datetime.datetime.now()
					flvData = self.DecodeFragment(data, fragNum, None)
					#flv = self.WriteFlvFile("C:/" + self.baseFilename + ".flv", self.audio, self.video)
					self.dataWritten = True
					flv = self.WriteFlvFile(self.outputfile, self.audio, self.video)
					flv.write(flvData)
				else:
					self.DecodeFragment(data, fragNum, flv)
				

			self.dataQueue.task_done()

		if self.pipeHandle:
			self.pipeHandle.Close()
			self.pipeHandle = None
		exit(-1)
		
	def runDataThread(self):
	        listeUserAgents = [ 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_5; fr-fr) AppleWebKit/525.18 (KHTML, like Gecko) Version/3.1.2 Safari/525.20.1',
        	                                        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/14.0.835.186 Safari/535.1',
                	                                'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/525.13 (KHTML, like Gecko) Chrome/0.2.149.27 Safari/525.13',
                        	                        'Mozilla/5.0 (X11; U; Linux x86_64; en-us) AppleWebKit/528.5+ (KHTML, like Gecko, Safari/528.5+) midori',
                                	                'Mozilla/5.0 (Windows NT 6.0) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/13.0.782.107 Safari/535.1',
                                        	        'Mozilla/5.0 (Macintosh; U; PPC Mac OS X; en-us) AppleWebKit/312.1 (KHTML, like Gecko) Safari/312',
                                                	'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11',
	                                                'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.8 (KHTML, like Gecko) Chrome/17.0.940.0 Safari/535.8' ]
		# Init curl
		c = pycurl.Curl()
		data = CurlData()
		c.setopt(c.WRITEFUNCTION, data.body_callback)
		c.setopt(pycurl.TIMEOUT, 30)
		# Set up user agent
		c.setopt(c.USERAGENT, random.choice(listeUserAgents))
		# And proxy
		if self.proxy:
			if self.proxy[0] != socks.PROXY_TYPE_HTTP_NO_TUNNEL:
				# Set generic options
				c.setopt(c.PROXY, self.proxy[1])
				c.setopt(c.PROXYPORT, self.proxy[2])
				c.setopt(c.PROXYUSERPWD, "%s:%s" % (self.proxy[4],self.proxy[5]))
			if self.proxy[0] == socks.PROXY_TYPE_HTTP:
				c.setopt(c.PROXYTYPE_HTTP)
			elif self.proxy[0] == socks.PROXY_TYPE_SOCKS4:
				c.setopt(c.PROXYTYPE_SOCKS4)
			elif self.proxy[0] == socks.PROXY_TYPE_SOCKS5:
				# pycurl doesn't seem to define c.PROXYTYPE_SOCKS5_HOSTNAME, so use the URL prefix method instead
				c.setopt(c.PROXY, "socks5h://%s" % (self.proxy[1]))
				#c.setopt(c.PROXYTYPE_SOCKS5)
			
		# Set up our fragment vars
		segNum = self.segNum
		fragNum = self.fragNum
		retries = 3

		while not self.dataThreadKill:
			data.reset()
			if self.needNewBootstrap:
				# Download a new bit of bootstrap info
				c.setopt(c.URL, self.urlbootstrap)
				try:
					c.perform()	
					self.dataQueue.put((None, data.contents))
					self.needNewBootstrap = False
				except Exception as e:
					print "Curl failed to fetch new bootstrap data: %s" % e.strerror
			else:
				# Download the next fragment
				fragNum = fragNum + 1
				if (self.segNum > 1):
					if (fragNum > (segNum * self.fragsPerSeg)):
						segNum = segNum + 1
						# Segment change, update bootstrap to get new fragsPerSeg
						self.needNewBootstrap = True
					elif (fragNum <= ((segNum - 1) * self.fragsPerSeg)):
						segNum = segNum - 1
						# Segment change, update bootstrap to get new fragsPerSeg
						self.needNewBootstrap = True
				filename1 = (self.fragUrl + "Seg%d" + "-Frag%d") % (segNum, fragNum)
				c.setopt(c.URL, filename1)
				try:
					c.perform()
					if(len(data.contents) < 1000):
						print "No more data available - waiting a bit."
						time.sleep(0.5)
						fragNum = fragNum - 1
						continue
					retries = 3
					self.dataQueue.put((fragNum, data.contents))
				except Exception as e:
					retries = retries - 1
					if retries > 0:
						# If we're retrying, roll back the fragNum
						fragNum = fragNum - 1
					else:
						print "Couldn't download fragment %d" % fragNum
		c.close()

	def UpdateBootstrapInfoWithData(self, bootstrapData):
		bootstrapPos = 0
		origFragCount = self.fragCount
		self.ReadBoxHeader(bootstrapData, bootstrapPos, None, None)
		bootstrapPos = self.pos
		if (self.boxType == "abst"):
			self.ParseBootstrapBox(bootstrapData, bootstrapPos)
		if origFragCount == self.fragCount:
			self.needNewBootstrap = True
		else:
			print "New fragment count is: %d" % self.fragCount

	def UpdateBootstrapInfo(self, bootstrapUrl):
		retries = 0
		fragNum = self.fragCount
		while ((fragNum == self.fragCount) and (retries < 30)):
			bootstrapPos = 0
			try:
				bootstrapfile = self.navigator.getFile(bootstrapUrl)
			except:
				exit(-1)
			self.ReadBoxHeader(bootstrapfile, bootstrapPos, None, None);
			#print self.boxType
			bootstrapPos = self.pos
			if (self.boxType == "abst"):
				self.ParseBootstrapBox(bootstrapfile, bootstrapPos);
			else:
				exit(-1)
			if (fragNum == self.fragCount):
				time.sleep(0.5)
				retries = retries + 1
		if (retries == 30):
			print "Unable to update Bootstrap Information"
			exit (-1)


	def parseManifest( self ):
		try :
			tree          = xml.etree.ElementTree.fromstring( self.manifest )
			# Duration
			self.duration     = float( tree.find( "{http://ns.adobe.com/f4m/1.0}duration" ).text )
			self.media          = tree.findall( "{http://ns.adobe.com/f4m/1.0}bootstrapInfo" )[ -1 ]
			self.streamid = tree.findall( "{http://ns.adobe.com/f4m/1.0}media" )[ -1 ]
			# Bootstrap URL
			self.urlbootstrap   = self.media.attrib[ "url" ]
		except :
			print( "Not possible to parse the manifest" )
			sys.exit( -1 )
		self.urlbootstrap = self.baseUrl + "/" + self.urlbootstrap
		try :
			bootstrapfile = self.navigator.getFile(self.urlbootstrap)
		except :
			print( "Not possible to get the bootstrap file")
			sys.exit( -1 )
		self.ReadBoxHeader(bootstrapfile, self.pos, self.boxType, self.boxSize)
		if (self.boxType == "abst"):
			self.ParseBootstrapBox(bootstrapfile, self.pos)

	def ReadBoxHeader(self, input_str, pos, boxType, boxSize):
		if (pos is None):
			pos = 0
		self.boxSize = self.ReadInt32(input_str, pos)
		boxTypeString = (input_str[pos+4], input_str[pos+5], input_str[pos+6], input_str[pos+7])
		self.boxType = string.join(boxTypeString, "") 
		if (self.boxSize == 1):
			self.boxSize = self.ReadInt64(input_str, pos+8) -16
			pos = pos + 16;
		else:
			self.boxSize = self.boxSize - 8
			pos = pos + 8
		self.pos = pos
		
	def ParseBootstrapBox(self, bootstrapinfo, pos):
		version = self.ReadByte(bootstrapinfo, pos)
		flags = self.ReadInt24(bootstrapinfo, (pos+1))
		bootstrapVersion = self.ReadInt32(bootstrapinfo, (pos + 4))
		byte = self.ReadByte(bootstrapinfo, (pos + 8))
		profile = (byte & 0xC0) >> 6
		self.live = (byte & 0x20) >> 5
		update = (byte & 0x10) >> 4
		timescale = self.ReadInt32(bootstrapinfo, (pos + 9))
		currentMediaTime = self.ReadInt64(bootstrapinfo, 13)
		smpteTimeCodeOffset = self.ReadInt64(bootstrapinfo, 21)
		pos = pos + 29
		movieIdentifier = self.ReadString(bootstrapinfo, pos)
		pos = self.pos
		serverEntryCount = self.ReadByte(bootstrapinfo, pos)
		pos += 1
		qualityEntryCount = self.ReadByte(bootstrapinfo, pos)
		pos += 1
		drmData = self.ReadString(bootstrapinfo, pos)
		pos = self.pos
		metadata = self.ReadString(bootstrapinfo, pos)
		pos = self.pos
		segRunTableCount = self.ReadByte(bootstrapinfo, pos)
		pos = pos + 1
		for i in range(0, segRunTableCount):
			self.ReadBoxHeader(bootstrapinfo, pos, self.boxType, self.boxSize)
			i=i+1
			if (self.boxType == "asrt"):
				self.ParseAsrtBox(bootstrapinfo, self.pos)
				#print "ASRT"
			pos = self.pos + self.boxSize
		fragRunTableCount = self.ReadByte(bootstrapinfo, pos)
		pos = pos + 1
		for i in range(0, fragRunTableCount):
			self.ReadBoxHeader(bootstrapinfo, pos, self.boxType, self.boxSize)
			i=i+1
			if (self.boxType == "afrt"):
				self.ParseAfrtBox(bootstrapinfo, self.pos)
			pos = self.pos + self.boxSize
		self.pos = pos

	
	def ReadInt32(self, input_str, pos):
		int32 = struct.unpack(">I", input_str[pos] + input_str[pos+1] + input_str[pos+2] + input_str[pos+3])[0]
		return int32

	def ReadInt24(self, input_str, pos):
		int24 = struct.unpack(">I", '\x00' + input_str[pos] + input_str[pos+1] + input_str[pos+2])[0]
		return int24
	
	def ReadByte(self, input_str, pos):
		unpacked_int = struct.unpack("B", input_str[pos])[0];
		return unpacked_int

	def ReadInt64(self, input_str, pos): 
		#hi = sprintf("%u", self.ReadInt32(str, pos))
		#lo = sprintf("%u", self.ReadInt32(str, pos + 4))
		hi = self.ReadInt32(input_str, pos)
		lo = self.ReadInt32(input_str, pos + 4)
		int64 = (hi * 4294967296 ) + lo
		#int64 = bcadd(bcmul(hi, "4294967296"), lo)
		return int64
		
	def ReadString(self, frag, fragPos):
		strlen = 0
		while (frag[fragPos + strlen] != "\x00"):
			strlen += 1
		str = frag[fragPos: strlen]
		fragPos += strlen + 1
		self.pos = fragPos
		return str
		
	def ParseAsrtBox(self, asrt, pos):
		version = self.ReadByte(asrt, pos)
		flags = self.ReadInt24(asrt, (pos + 1))
		qualityEntryCount = self.ReadByte(asrt, (pos + 4))
		pos = pos + 5
		for i in range (0, qualityEntryCount):
			#qualitySegmentUrlModifiers[i] = self.ReadString(asrt, pos)
			i = i+1
		self.segCount = self.ReadInt32(asrt, pos)
		self.segTable = dict( ((i,j),None) for i in range(self.segCount) for j in range(2) )
		pos = pos + 4
		for i in range (0, self.segCount):
			firstSegment = self.ReadInt32(asrt, pos)
			fragmentsPerSegment = self.ReadInt32(asrt, (pos + 4))
			self.segTable[i, 0] = firstSegment
			self.segTable[i, 1] = fragmentsPerSegment
			pos = pos+8
			i=i+1
		lastSegment = self.segTable[self.segCount-1, 0]
		self.fragCount = self.segTable[self.segCount-1, 1]
		if (self.live == 1) and (self.segCount >1):
			try:
				secondLastSegment = self.segCount-2
			except:
				pass
			if self.fragNum is None:
				self.segNum = lastSegment
				self.fragsPerSeg = self.segTable[secondLastSegment, 1]
				self.fragNum = self.segTable[secondLastSegment,0] * self.fragsPerSeg + self.fragCount - 2;
				self.fragCount = self.segTable[secondLastSegment,0] * self.fragsPerSeg + self.fragCount;
			else:
				self.fragCount = self.segTable[secondLastSegment,0] * self.fragsPerSeg + self.fragCount;
			
	def ParseAfrtBox(self, afrt, pos):
		version = self.ReadByte(afrt, pos)
		flags = self.ReadInt24(afrt, pos + 1)
		timescale = self.ReadInt32(afrt, pos + 4)
		qualityEntryCount = self.ReadByte(afrt, pos + 8)
		pos = pos + 9
		self.fragEntries = self.ReadInt32(afrt, pos)
		self.fragTable = dict( ((i,j),None) for i in range(self.fragEntries) for j in range(4) )
		pos = pos + 4
		for i in range (0, self.fragEntries):
			firstFragment = self.ReadInt32(afrt, pos)
			self.fragTable[i,0] = firstFragment
			self.fragTable[i,1] = self.ReadInt64(afrt, pos + 4)
			self.fragTable[i,2] = self.ReadInt32(afrt, pos + 12)
			self.fragTable[i,3] = ""
			pos += 16
			if self.fragTable[i,2] == 0:
				self.fragTable[i,3] = self.ReadByte(afrt, pos)
				pos = pos + 1
			i = i + 1
		if self.segCount == 1:
			firstFragment = 0
			lastFragment = self.fragEntries
			if self.live == 1:
				if self.fragNum is None:
					self.fragNum = self.fragTable[lastfragment, 0] - 2
					self.fragCount = self.fragTable[firstFragment, 0]
				else:
					self.fragCount = self.fragTable[lastFragment,0]
			elif self.fragNum is None:
				self.fragNum = self.fragTable[firstFragment,0] - 1
				
				
	def DecodeFragment(self, frag, fragNum, flv):
		flvData = ""
		fragLen = 0
		fragPos = 0
		boxSize = 0
		fragLen = len(frag)
		packetTS = None
		while (fragPos < fragLen):
			self.ReadBoxHeader(frag, fragPos, None, None)
			if (self.boxType == "mdat"):
				fragPos = self.pos
				break
			fragPos = self.pos + self.boxSize
			
		while (fragPos < fragLen):
			packetType = self.ReadByte(frag, fragPos)
			packetSize = self.ReadInt24(frag, fragPos + 1)
			packetTS = self.ReadInt24(frag, fragPos + 4)
			packetTS = (packetTS | (self.ReadByte(frag, fragPos + 7) << 24))
			if (packetTS & 0x80000000):
				packetTS &= 0x7FFFFFFF
				#self.WriteFlvTimestamp(frag, fragPos, packetTS)
			if ((self.baseTS is False) and ((packetType == 0x08) or (packetType == 0x09))):
				self.baseTS = packetTS
			totalTagLen = self.tagHeaderLen + packetSize + self.prevTagSize
			
			if packetType == 0x08:
				if (packetTS >= self.prevAudioTS - self.TIMECODE_DURATION * 5):
					FrameInfo = self.ReadByte(frag, fragPos + self.tagHeaderLen)
					CodecID = (FrameInfo & 0xF0) >> 4
					if (CodecID == 0x0A):
						AAC_PacketType = self.ReadByte(frag, fragPos + self.tagHeaderLen + 1)
						if (AAC_PacketType == 0x00):
							if (self.AAC_HeaderWritten is True):
								#break
								i = 1
								#print "Skipping"
							else:
								#print("Writing AAC sequence header")
								self.AAC_HeaderWritten = True
								self.prevAAC_Header = True
						elif (self.AAC_HeaderWritten is False):
							i = 1
							#print("Discarding audio packet received before AAC sequence header",)
							#break
					if (packetSize > 0):
						#Check for packets with non-monotonic audio timestamps and fix them
						if ((self.prevAAC_Header is False) and (packetTS <= self.prevAudioTS)):
							#print ("Fixing audio timestamp")
							packetTS = packetTS + self.TIMECODE_DURATION + (self.prevAudioTS - packetTS)
							#self.WriteFlvTimestamp(frag, fragPos, packetTS)
						if ((CodecID == 0x0A) and (AAC_PacketType != 0x00)):
							self.prevAAC_Header = False
						if (flv):
							#pAudioTagPos = flv.tell()
							if xbmc.Player().isPlaying():
								flvData = frag[fragPos: fragPos + totalTagLen]
								flv.write(flvData)
							else:
								self.stop = datetime.datetime.now()
								elapsed = self.stop - self.start
								if (elapsed > datetime.timedelta(seconds=25)):
									self.dataThreadKill = True
									print "Downloads Killed"
									exit(-1)
								else:
									flvData = frag[fragPos: fragPos + totalTagLen]
                                                        		flv.write(flvData)
							#flvData = frag[fragPos: fragPos + totalTagLen]
							#flv.write(flvData)
							
						else:
							#flvData .= substr($frag, $fragPos, $totalTagLen);
							flvData = flvData + frag[fragPos: fragPos + totalTagLen]
						self.prevAudioTS = packetTS
						pAudioTagLen = totalTagLen
					else:
						i = 1
						#print ("Skipping small sized audio packet")
				else:
					i= 1
					#print "Test"
				if (self.audio is False):
					self.audio = True
				#break
				
			elif packetType == 0x09:
				if (packetTS >= self.prevVideoTS - self.TIMECODE_DURATION * 5):
					FrameInfo = self.ReadByte(frag, fragPos + self.tagHeaderLen)
					FrameType = (FrameInfo & 0xF0) >> 4
					CodecID = FrameInfo & 0x0F
					if (FrameType == 0x05):
						printf("Skipping video info frame")
					if (CodecID == 0x07):
						AVC_PacketType = self.ReadByte(frag, fragPos + self.tagHeaderLen + 1)
						if (AVC_PacketType == 0x00):
							if (self.AVC_HeaderWritten is True):
								i = 1
								#print ("Skipping AVC sequence header")
							else:
								#print("Writing AVC sequence header")
								self.AVC_HeaderWritten = True
								self.prevAVC_Header = True
						elif (self.AVC_HeaderWritten is False):
							i = 1
							#print ("Discarding video packet received before AVC sequence header")
				if (packetSize > 0):
					#Check for packets with non-monotonic video timestamps and fix them
					if ((self.prevAVC_Header is False) and ((CodecID == 0x07) and (AVC_PacketType != 0x02)) and (packetTS <= self.prevVideoTS)):
						#print("Fixing video timestamp")
						packetTS = packetTS + self.TIMECODE_DURATION + (self.prevVideoTS - packetTS)
						#self.WriteFlvTimestamp(frag, fragPos, packetTS)
					if ((CodecID == 0x07) and (AVC_PacketType != 0x00)):
						self.prevAVC_Header = False
					if (flv):
						if xbmc.Player().isPlaying():
							flvData = frag[fragPos: fragPos + totalTagLen]
							flv.write(flvData)
						else:
							self.stop = datetime.datetime.now()
                                                        elapsed = self.stop - self.start
                                                        if (elapsed > datetime.timedelta(seconds=25)):
								                            self.dataThreadKill = True
                                                        	print "Downloads Killed"
                                                                exit(-1)
                                                        else:
                                                        	flvData = frag[fragPos: fragPos + totalTagLen]
                                                        	flv.write(flvData)
							#flvData = frag[fragPos: fragPos + totalTagLen]
                                                        #flv.write(flvData)
							#exit(-1)
						#flvData = frag[fragPos: fragPos + totalTagLen]
						#flv.write(flvData)
						#pVideoTagPos = flv.tell()
						#fwrite($flv, substr($frag, $fragPos, $totalTagLen), $totalTagLen)
					else:
						#flvData .= substr($frag, $fragPos, $totalTagLen)
						flvData = flvData + frag[fragPos:fragPos+totalTagLen]
						
					self.prevVideoTS = packetTS
					pVideoTagLen = totalTagLen
				else:
					print ("Skipping small sized video packet")
				if (self.video is False):
					self.video = True
				#break

			elif packetType == 0x12:
				i = 1
				#print "SCRIPT DATA"
			
			else:
				print packetType
				print "Scrambled stream"
				exit (-1)
			
			fragPos = fragPos +  totalTagLen
		if (self.baseTS is not False and packetTS):
			self.duration = round((packetTS - self.baseTS) / 1000, 0)
		return flvData
			
			
	def WriteFlvFile(self, outFile, audio, video):
		print outFile
		flvHeader = self.flvHeader
		if ((video is False) or (audio is False)):
			if ((audio is True) & (video is False)):
				flvHeader[4] = "\x04"
			elif ((video is True) & (audio is False)):
				flvHeader[4] = "\x01"
		flv = open(outFile, "a+b");
		if (flv is False):
			print("Failed to open ")
			exit(-1)
		#flv.write(flvHeader, self.flvHeaderLen)
		flv.write(flvHeader)
		#self.WriteMetadata(flv)
		return flv







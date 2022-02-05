#! /usr/bin/python
import urllib2
import sys
import socket
import binascii
from netmsg import netmsg

CONFADDR = 'http://localhost/tsweb/axsystem'
ATTADDR = 'http://localhost/tsweb/axatt'
MYIP = "192.168.1.12"
SIPPORT = 5060
RTPRECV = 7000
CALLID = '00000000'
ATEXT = '000' 

DIGITTAB = {}

def getConfig() :
    # Get config from server
    global MYIP,SIPPORT
    website = urllib2.urlopen(CONFADDR)
    website_html = website.read()

    for line in website_html.split('\n') :
        line =  line.lstrip().split(' ')
        if '<ipaddr>' ==  line[0] :
            print 'config ipaddr =',line[1]
            MYIP = line[1]
        if '<sipport>' ==  line[0] :
            print 'config sipport =',line[1]
            SIPPORT = int(line[1])

def getDigits() :
    # RTP digit table builder
    global DIGITTAB
    URL = ATTADDR+"?ext="+ATEXT
    print "Url",URL
    website = urllib2.urlopen(URL)
    website_html = website.read()
    #print website_html
    for line in website_html.split('\n') :
        line =  line.lstrip().split(' ')
        if '<number>' ==  line[0] :
            TOEXT = line[1]
        if '<state>' ==  line[0] :
            DIGIT = line[1]
        if '</attdata>' ==  line[0] :
            DIGITTAB[DIGIT] = TOEXT
            print "Added:",DIGIT,"Ext:",TOEXT

def digitLookup(digit) :
    # RTP Digit lookup
    if digit in DIGITTAB : return DIGITTAB[digit]
    print "No match"
    return None 
#
# Currently the outgoing port is taken from the incoming 
# The timing is determined from the incoming packets
# 
def rtpserv() :
    PLAYING = True
    DIGIT = None	# single digit
    TIMEOUT = True	# Timer on
    DIGITS = ''		# digit string
    COUNT = 500
    #recfile = open('record.wav', 'w')
    playfile = open('message.wav', 'r')

    while PLAYING:
	recvdata = RTPMSG.recvmsg()
        HEAD = binascii.hexlify(recvdata[:16])
        #print HEAD
        if ord(recvdata[1]) == 101 : # tel codec
            #print HEAD
            DIGIT = binascii.hexlify(recvdata[12])	
            COUNT = 10 		# Debounce 10 packets
            #print "Digit: ",DIGIT
        else :
            if COUNT > 0 : COUNT -= 1
            if COUNT == 0 :
                # Timer expired
                print "Expired"
                if not DIGIT : 		
                    if TIMEOUT : DIGITS = '7' 
                    if len(DIGITS) == 1 :	# single
                        EXT = digitLookup(DIGITS)
                        if EXT :
                            response = 'TRANSFER ' + '\r\nCall-ID: ' + CALLID  + '\r\nExtn: ' + EXT + '\r\n\r\n'
                            SIPMSG.setfrom(MYIP,SIPPORT)
                            SIPMSG.sendmsg(response)
                            PLAYING = False
                        DIGITS = ''
                    if len(DIGITS) > 1 :	# multi
                        response = 'TRANSFER ' + '\r\nCall-ID: ' + CALLID  + '\r\nExtn: ' + DIGITS + '\r\n\r\n'
                        SIPMSG.setfrom(MYIP,SIPPORT)
                        SIPMSG.sendmsg(response)
                        PLAYING = False
                        #DIGITS = ''
                    COUNT = -1
                else :
                    # Got a digit
                    print "Digit",DIGIT
                    TIMEOUT = False
                    if DIGIT == '0b' : # restart message
                        # Built in functionality
                        playfile.close()
                        playfile = open('message.wav', 'r')
                        COUNT = -1
                        DIGIT = None
                    else : 
                        DIGITS = DIGITS + DIGIT.lstrip('0')
                        COUNT = 100		# inter digit timer
                        DIGIT = None

            #recfile.write(recvdata[12:])
            playdata = playfile.read(160)
            if playdata != '' :
                data = recvdata[:12] + playdata
	        RTPMSG.sendmsg(data)

if len(sys.argv) > 1 :
    RTPRECV = int(sys.argv[1])
if len(sys.argv) > 2 :
    CALLID = sys.argv[2]
if len(sys.argv) > 3 :
    ATEXT = sys.argv[3]
print "RTP recv port:",RTPRECV,"Callid:",CALLID,"Atext:",ATEXT
getConfig()
getDigits()
SIPMSG=netmsg(MYIP,SIPPORT)
RTPMSG=netmsg(MYIP,RTPRECV)
RTPMSG.bind()
rtpserv()

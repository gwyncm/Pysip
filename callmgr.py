#! /usr/bin/python
import psycopg2
import urllib2
import copy
import signal
import os
import subprocess
import sys
import re
from netmsg import netmsg
from msglib import callmgr,call,sipext

CONFADDR = 'http://localhost/tsweb/axsystem'
MYIP = '192.168.1.12'
MYPORT = 5060
EXTDB = {}

# 
# Get server config
#
def getConfig() :
    # Get config from server
    global MYIP,MYPORT
    website = urllib2.urlopen(CONFADDR)
    website_html = website.read()

    for line in website_html.split('\n') :
        line =  line.lstrip().split(' ')
        if '<ipaddr>' ==  line[0] :
            print 'config ipaddr =',line[1]
            MYIP = line[1]
        if '<sipport>' ==  line[0] :
            print 'config sipport =',line[1]
            MYPORT = int(line[1])
#
# Database reread
#
def handler(signum, frame):
    print "Rereading Database"

#
# Message server application
#
def msgServer() :

    signal.signal(signal.SIGHUP, handler)

    getConfig()

    NETMSG=netmsg(MYIP,MYPORT)
    NETMSG.bind()
    CM = callmgr(NETMSG)
    CM.dbInit()
    CM.dbLoad()
    CM.dbCall('111')

    while 1:
        try:
	    data = NETMSG.recvmsg()
        except KeyboardInterrupt:
            print
            print "Program Ending"
            CM.printCallDB()
            CM.rtpStop()
            exit()
        except :
            CM.dbLoad()
            print "Restarting"
            continue

	MSGD = CM.msgParse(data) 
        MSGD['Ipaddr'] = NETMSG.fromaddr
        MSGD['Port'] = NETMSG.fromport
        COMMAND = MSGD['Command']
        RESPONSE = MSGD['Response']
        RESPTEXT = MSGD['Resptext']

        if COMMAND == 'JAK' : continue		# Linphone keepalive

        SC = CM.getCall(MSGD)

        SDP = '' 
        if 'sdp' in MSGD :
            if MSGD['sdp'] != '' : SDP = ' ** With SDP'
        print '<-- {',NETMSG.fromaddr,':',NETMSG.fromport,'} ',COMMAND,':',RESPONSE,RESPTEXT,' Callstate: ',SC.CALLSTATE,' Callid: ',SC.CALLID,SDP
#
# Sip message handling
#
        if COMMAND == 'TRANSFER' : CM.rtpMessage(SC,MSGD)	
        if COMMAND == 'TRANSFER'  : SC.holdCaller(MSGD)
        if COMMAND == 'TRANSFER'  : SC.callState('RTPHOLD')

        if COMMAND == 'OPTIONS'   : SC.okOptions(MSGD)
        if COMMAND == 'OPTIONS'   : CM.endCall(SC)
        if COMMAND == 'REGISTER'  : CM.okRegister(SC,MSGD)
        if COMMAND == 'REGISTER'  : CM.endCall(SC)
        if COMMAND == 'SUBSCRIBE' : SC.okSubscribe(MSGD)
        if COMMAND == 'SUBSCRIBE' : CM.endCall(SC)
        if COMMAND == 'INFO'      : SC.okSender(MSGD)
        if COMMAND == 'NOTIFY'    : SC.okSender(MSGD)
        if COMMAND == 'PUBLISH'   : SC.okSender(MSGD)
        if COMMAND == 'CANCEL'    : SC.okSender(MSGD)
        if COMMAND == 'BYE'       : SC.okSender(MSGD)
    
        if RESPONSE == '481'      : SC.ackSender(MSGD)	# CALL LEG/TRANSACTION DOES NOT EXIST
        if RESPONSE == '491'      : SC.ackSender(MSGD)	# SERVER INTERNAL ERROR
        if RESPONSE == '480'      : SC.ackSender(MSGD)	# TEMPORARILY UNAVAILABLE
        if RESPONSE == '487'      : SC.ackSender(MSGD)	# REQUEST CANCELLED
        if RESPONSE == '603'      : SC.ackSender(MSGD)	# DECLINE
        if RESPONSE == '486'      : SC.ackSender(MSGD)	# BUSY HERE
#
# State based messages
# 
        if SC.CALLSTATE == 'IDLE'     : 
            if COMMAND == 'INVITE'         : SC.sendTrying(MSGD)	
            if COMMAND == 'INVITE'         : CM.extLookup(SC,MSGD)	# Do this first
            if COMMAND == 'INVITE'         : SC.saveCaller(MSGD)	
            if COMMAND == 'INVITE'         : SC.sendInvite(MSGD)	
            continue
    
        if SC.CALLSTATE == 'TRYING'   : 
            if RESPONSE == '180'           : SC.saveCalled(MSGD)	# Save called totag
            if RESPONSE == '180'           : SC.sendRinging(MSGD)	# Ring calling party

            if COMMAND  == 'CANCEL'        : SC.sendCancel()		# Cancel called party
            if COMMAND  == 'CANCEL'        : SC.callState('BYE')

            if RESPONSE == '603'           : SC.sendDecline()		# Decline calling party
            if RESPONSE == '603'           : SC.callState('BUSY')	# DECLINE

            if RESPONSE == '486'           : SC.sendBusy()		# Busy calling party
            if RESPONSE == '486'           : SC.callState('BUSY')	# BUSY HERE

            if RESPONSE == '200'           : SC.saveCalled(MSGD) 	# Save called message
            if RESPONSE == '200'           : SC.okOther(MSGD)    	# Answer caller
            if RESPONSE == '200'           : SC.callState('ANSWER')
            continue
    
        if SC.CALLSTATE == 'BUSY'    : 
            if COMMAND ==  'ACK'           : CM.endCall(SC)
            continue
    
        if SC.CALLSTATE == 'ANSWER'  : 
            if COMMAND ==  'ACK'           : SC.ackCalled(0)		# Connect caller
            if COMMAND ==  'ACK'           : SC.callState('CONNECTED')
            continue
    
        if SC.CALLSTATE == 'CONNECTED' : 
            if COMMAND  == 'INVITE'        : SC.sendTrying(MSGD)	
            if COMMAND  == 'INVITE'        : SC.holdOther(MSGD)
            if COMMAND  == 'INVITE'        : SC.callState('PREHOLD')

            if COMMAND  == 'BYE'           : SC.byeOther(MSGD) 
            if COMMAND  == 'BYE'           : SC.callState('BYE')
            continue
    
        if SC.CALLSTATE == 'PREHOLD' : 
            if RESPONSE == '200'           : SC.ackSender(MSGD)	
            if RESPONSE == '200'           : SC.okOther(MSGD)
            if RESPONSE == '200'           : SC.callState('HOLD')
            continue
    
        if SC.CALLSTATE == 'HOLD'    : 
            if COMMAND  == 'INVITE'        : SC.sendTrying(MSGD)	
            if COMMAND  == 'INVITE'        : SC.holdOther(MSGD)		# Unhold
            if COMMAND  == 'INVITE'        : SC.callState('UNHOLD')

            if COMMAND  == 'REFER'         : SC.refAccept(MSGD)
            if COMMAND  == 'REFER'         : SC.refOther(MSGD)
            if COMMAND  == 'REFER'         : SC.callState('REFER')
            continue
    
        if SC.CALLSTATE == 'UNHOLD'  : 
            if RESPONSE == '200'           : SC.ackSender(MSGD)	
            if RESPONSE == '200'           : SC.okOther(MSGD)
            if RESPONSE == '200'           : SC.callState('CONNECTED')
            continue
    
        if SC.CALLSTATE == 'NOTIFY'  : 
            if RESPONSE == '200'           : SC.callState('CONNECTED')

        if SC.CALLSTATE == 'REFER'  : 					# Must be after Notify
            if COMMAND  == 'NOTIFY'        : SC.refNotify(MSGD)	
            if RESPONSE == '200'           : SC.callState('NOTIFY')

        if SC.CALLSTATE == 'BYE'     : 
            if RESPONSE == '200'           : CM.endCall(SC)
            continue
#
#  Audio transfer
#
        if SC.CALLSTATE == 'RTPANSWER'  : 
            if COMMAND ==  'ACK'           : SC.rtpStart()		
            if COMMAND ==  'ACK'           : SC.callState('RTPCONNECT')
            continue

        if SC.CALLSTATE == 'RTPCONNECT' : 
            if COMMAND  == 'BYE'           : SC.rtpStop() 
            if COMMAND  == 'BYE'           : SC.callState('BYE')
            continue
    
        if SC.CALLSTATE == 'RTPHOLD' : 
            if RESPONSE == '200'           : SC.ackSender(MSGD)	
            if RESPONSE == '200'           : SC.refCaller(MSGD)	
            if RESPONSE == '200'           : SC.callState('RTPREFER')
            continue

        if SC.CALLSTATE == 'RTPREFER' : 
            if RESPONSE == '202'           : SC.callState('RTPNOTIFY')
            continue

        if SC.CALLSTATE == 'RTPNOTIFY' : 
            if COMMAND  == 'NOTIFY'        : CM.endCall(SC)
            continue
#
# Waiting states
#    
        if SC.CALLSTATE == 'PREWAIT' : 
            if RESPONSE == '200'           : SC.ackCalled(1)    	
            if RESPONSE == '200'           : SC.callState('WAITING')

    NETMSG.close()
   
msgServer()

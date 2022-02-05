#! /usr/bin/python
import copy,json
import urllib2
import subprocess
from netmsg import netmsg

FLDLIST = [ 'Via', 'From', 'To', 'Call-ID', 'CSeq', 'Contact', 'Allow', 'Max-Forwards', 'User-Agent', 'Expires', 
                   'Supported', 'Event', 'Subscription-State', 'Refer-To', 'Referred-By', 'Replaces' ]
ALLOW = [ 'REGISTER', 'SUBSCRIBE', 'INVITE', 'CANCEL', 'NOTIFY', 'OPTIONS', 'BYE', 'ACK', 'REFER', 'RTPMSG', 'INFO', 'PUBLISH' ]
REGTIME = '3600'	# Registration timer
EXTADDR = 'http://localhost/tsweb/axext'
JEXTADDR = 'http://localhost/tsweb/jsext'
JEXTCLADDR = 'http://localhost/tsweb/jsextcl?ext='

#
# Call MGR 
#
class callmgr :
  def __init__(self,netmsg) :
    self.NETMSG = netmsg 
    self.MYIP = netmsg.ipaddr 		# Servers IP
    self.RTPPORT = 7050
    self.CALLDB = {}
    EXTDB = {}
    EXTCL = {}

  def endCall(self,sc) :
    if sc.CALLID in self.CALLDB :
        sc.EXT1.BUSY = False
        sc.EXT2.BUSY = False
        del self.CALLDB[sc.CALLID]
        
  def rtpStop(self) :
    # Stop all rtp processes
    for key in self.CALLDB :
        self.CALLDB[key].rtpStop()

  def getCall(self,MSGD) :
    # Get a call object
    #print 'Getcall: ',MSGD['Call-ID']
    if MSGD['Call-ID'] in self.CALLDB :
        # Existing call
        SC = self.CALLDB[MSGD['Call-ID']]
        #print "Existing call: ",SC.CALLID," Call state: ",SC.CALLSTATE
    else :
        # New call 
        SC = call(MSGD['Call-ID'],self.NETMSG)
        self.RTPPORT += 1
        if self.RTPPORT > 7090 : self.RTPPORT = 7050
        SC.RTPPORT = "{0}".format(self.RTPPORT)
        self.CALLDB[SC.CALLID] = SC
        #print "New call: ",SC.CALLID," Call state: ",SC.CALLSTATE
    return SC

  def extLookup(self,SC,MSGD) :
    # Lookup extensions 
    NUMBER = MSGD['Fromext']
    if NUMBER in self.EXTDB :
        SC.EXT1 = self.EXTDB[NUMBER]
    else :
        SC.EXT1 = sipext(NUMBER,self.NETMSG)
        print "EXT1 number not found"
    #SC.EXT1.IPADDR = self.NETMSG.fromaddr
    #SC.EXT1.PORT = self.NETMSG.fromport
    NUMBER = MSGD['Toext']
    if NUMBER in self.EXTDB :
        SC.EXT2 = self.EXTDB[NUMBER]
    else :
        SC.EXT2 = sipext(NUMBER,self.NETMSG)
        print "EXT2 number not found"
    SC.EXT2.PARTY = 1

  def rtpMessage(self,SC,MSGD) :
    # RTP transfer message
    SC.rtpStop()
    NUMBER = MSGD['Extn']
    if NUMBER in self.EXTDB :
        SC.EXT3 = self.EXTDB[NUMBER]
    else :
        SC.EXT3 = sipext(NUMBER,self.NETMSG)
        print "EXT3 number not found"
        self.EXT3.PARTY = 1

  def okRegister(self,SC,MSGD) :
    # Respond to register
    EXT = MSGD['Fromext']
    IP = MSGD['Ipaddr']
    PORT = MSGD['Port']
    print "Register ext:",EXT,"IP:",IP,"Port:",PORT
    # Update database?
    if EXT in self.EXTDB :
        self.EXTDB[EXT].IPADDR = IP
        self.EXTDB[EXT].PORT = int(PORT)
    MSGD['Expires'] = REGTIME
    SC.EXT1.sendMsg(MSGD,'SIP/2.0 200 OK','')

  def printCallDB(self) :
    print "Status    |From Ext  |To Ext    |State     |Callid"
    print "------------------------------------------------------------------------------------"
    for key in self.CALLDB :
        status = 'ACTIVE'
        print "{0:10}|{1:10}|{2:10}|{3:10}|{4}".format(
            status,self.CALLDB[key].EXT1.NUMBER,self.CALLDB[key].EXT2.NUMBER,self.CALLDB[key].CALLSTATE,key)
    print

  def dbInit(self) :
    # Fake initial db if no server
    EXT1 = sipext('113',self.NETMSG)
    EXT1.IPADDR = '192.168.1.53'
    EXT2 = sipext('211',self.NETMSG)
    EXT2.IPADDR = '192.168.1.141'
    self.EXTDB = {'113' : EXT1, '211' : EXT2 }

  def dbCall(self,ext) :
    # Get extdb from server
    website = urllib2.urlopen(JEXTCLADDR+ext)
    website_html = website.read()
    extcls =  json.loads(website_html)
    for extcl in extcls :
        print "Ext:",ext,"Number:",extcl['number'],"Action:",extcl['action'],"Id:",extcl['id'],"Rings:",extcl['rings'],"State:",extcl['state'],"Mode:",extcl['mode']

  def dbLoad(self) :
    # Get extdb from server
    website = urllib2.urlopen(JEXTADDR)
    website_html = website.read()
    exts =  json.loads(website_html)
    for ext in exts :
        number = ext['number']
        EXT = sipext(number,self.NETMSG)
        EXT.IPADDR = ext['ipaddr']
        EXT.PORT = int(ext['port'])
        EXT.TYPE = ext['type']
        if EXT.IPADDR  == '0.0.0.0' : EXT.IPADDR  = self.MYIP
        if EXT.PORT == 0 : EXT.PORT = 5060
        self.EXTDB[number] = EXT
        print "Ext:",number,"Type:",EXT.TYPE,"Ipaddr:",EXT.IPADDR,"Port:",EXT.PORT
        self.dbCall(number)

  def dbLoad2(self) :
    # Get extdb from server
    website = urllib2.urlopen(EXTADDR)
    website_html = website.read()

    for line in website_html.split('\n') :
        line =  line.lstrip().split(' ')
        if '<number>' ==  line[0] :
            number = line[1]
        if '<type>' ==  line[0] :
            type = line[1]
        if '<ipaddr>' ==  line[0] :
            ipaddr = line[1]
        if '<port>' ==  line[0] :
            port = line[1]
        if '</extension>' ==  line[0] :
            if ipaddr == '0.0.0.0' : ipaddr = self.MYIP
            if port == '0' : port = '5060'
            print "Ext:",number,"Type:",type,"Ipaddr:",ipaddr,"Port:",port
            EXT = sipext(number,self.NETMSG)
            EXT.IPADDR = ipaddr
            EXT.PORT = int(port)
            EXT.TYPE = type
            self.EXTDB[number] = EXT


  def msgParse(self,msg) :
    # Parse a message
    COMMAND = msg[0:msg.find(' ')].upper()
    RESPONSE = ''
    RESPTEXT = ''
    if COMMAND == 'SIP/2.0' :
        RESPONSE = msg[0:msg.find('\r')].upper()
        RESPTEXT = ' '.join(RESPONSE.split(' ')[2:])
        RESPONSE = RESPONSE.split(' ')[1] 
    MSGD = { 'Command': COMMAND, 'Response': RESPONSE, 'Resptext' : RESPTEXT, 'Call-ID': '0000000000',
             'Fromext' : '', 'Toext' : '' }
    if COMMAND not in ALLOW  and COMMAND != 'SIP/2.0': return MSGD
    sdp = ''
    nmsg = msg.replace('\r','')    
    lines = nmsg.split('\n')
    for l in lines :
        if l != '' and l[1] == '=': sdp = sdp + l + '\r\n'
        else :
            index = l.find(':')
            if index > 0 :
                key = l[0:index].lstrip()
                MSGD[key] = l[index+1:].lstrip()
    MSGD['sdp'] = sdp
    if 'From' in MSGD :
        if '@' in MSGD['From'] : MSGD['Fromext']  = MSGD['From'].split(':')[1].split('@')[0]
    if 'To' in MSGD :
        MSGD['Toext'] = MSGD['To'].split(':')[1].split('@')[0]
    #print MSGD
    #print sdp
    return MSGD
#
# Sip Extension 
#
class sipext :
  def __init__(self,number,netmsg) :
    self.NUMBER = number
    self.IPADDR = ''
    self.PORT = 5060
    self.TYPE = '0'
    self.PARTY = 0
    self.BUSY = False
    self.SAVEMSG = {}
    self.NETMSG = netmsg 
    self.MYIP = netmsg.ipaddr 		# Servers IP
    self.MYPORT = netmsg.port		# Servers port
  
  def sendMsg(self,msgd,header,sdps) :
    # Send generic response
    response = self.msgGen(msgd,header,sdps)
    self.NETMSG.sendmsg(response)
    
  def sendOk(self,sdps) :
    # Send OK
    MSGD = self.SAVEMSG
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    MSGD['Contact'] = '<sip:' + self.NUMBER + '@' + self.MYIP + '>'
    response = self.msgGen(MSGD,'SIP/2.0 200 OK',sdps)
    self.NETMSG.sendmsg(response)

  def sendAck(self,inc) :
    # Send Ack 
    MSGD = copy.deepcopy(self.SAVEMSG)
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} ACK".format(int(seq)+inc)
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'ACK sip:'+self.NUMBER+'@'+self.IPADDR+' SIP/2.0','')
    self.NETMSG.sendmsg(response)

  def sendRinging(self) :
    # Send ringing to caller
    TOTAG = '1122334455'
    MSGD = self.SAVEMSG
    MSGD['To'] = MSGD['To'] + ";tag={0}".format(TOTAG)
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'SIP/2.0 180 Ringing','')
    self.NETMSG.sendmsg(response)

  def sendBusy(self) :
    # Send busy to caller
    MSGD = self.SAVEMSG
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'SIP/2.0 468 Busy Here','')
    self.NETMSG.sendmsg(response)

  def sendDecline(self) :
    # Send decline to caller
    MSGD = self.SAVEMSG
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'SIP/2.0 603 Decline','')
    self.NETMSG.sendmsg(response)

  def sendHold(self,sdps) :
    # Send hold 
    MSGD = self.SAVEMSG
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} INVITE".format(int(seq)+1)
    MSGD['Contact'] = '<sip:' + self.NUMBER + '@' + self.MYIP + '>'
    if self.PARTY == 0 :
        MSGD = copy.deepcopy(self.SAVEMSG)
        to = MSGD['To']
        MSGD['To'] = MSGD['From']
        MSGD['From'] = to
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'INVITE sip:'+self.NUMBER+'@'+self.IPADDR+' SIP/2.0',sdps)
    self.NETMSG.sendmsg(response)

  def sendRefer(self,number) :
    # Send refer 
    MSGD = self.SAVEMSG
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} REFER".format(int(seq)+1)
    MSGD['Contact'] = '<sip:' + self.NUMBER + '@' + self.MYIP + '>'
    MSGD['Refer-To'] = '<sip:'+number+'@' + self.MYIP + '>'
    MSGD['Referred-By'] = '<sip:' + self.NUMBER + '@' + self.MYIP + '>'
    if self.PARTY == 1 :
        MSGD = copy.deepcopy(self.SAVEMSG)
        to = MSGD['To']
        MSGD['To'] = MSGD['From']
        MSGD['From'] = to
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'REFER sip:'+self.NUMBER+'@'+self.IPADDR+' SIP/2.0','')
    self.NETMSG.sendmsg(response)

  def sendBye(self) :
    # Bye the calling party
    MSGD = self.SAVEMSG
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} BYE".format(int(seq)+1)
    if self.PARTY == 0 :
        to = MSGD['To']
        MSGD['To'] = MSGD['From']
        MSGD['From'] = to
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'BYE sip:'+self.NUMBER+'@'+self.IPADDR+' SIP/2.0','')
    self.NETMSG.sendmsg(response)

  def sendInvite(self,number,callid,sdps) :
    # Send invite to called 
    MSGD = self.genInvite(number,callid)
    self.SAVEMSG = MSGD
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'INVITE sip:'+self.NUMBER+'@'+self.MYIP+' SIP/2.0',sdps)
    self.NETMSG.sendmsg(response)

  def sendTrying(self,msgd) :
    # Send trying to sender 
    response = self.msgGen(msgd,'SIP/2.0 100 TRYING','')
    self.NETMSG.sendmsg(response)

  def sendCancel(self) :
    # Cancel the called party
    MSGD = self.SAVEMSG
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} CANCEL".format(int(seq))
    self.NETMSG.setfrom(self.IPADDR,self.PORT)
    response = self.msgGen(MSGD,'CANCEL sip:'+self.NUMBER+'@'+self.IPADDR+' SIP/2.0','')
    self.NETMSG.sendmsg(response)

  def genAllow(self) :
    # Generate an allow list
    AL = ""
    for l in ALLOW :
        if AL != "" : AL = AL + ', '
        AL = AL + l
    return AL

  def msgGen(self,msgd,head,sdp) :
    length = len(sdp)
    if length > 0 :
        print '--> {',self.NETMSG.fromaddr,':',self.NETMSG.fromport,'} ',head,'Callid:',msgd['Call-ID'],' *** With SDP'
    else :
        print '--> {',self.NETMSG.fromaddr,':',self.NETMSG.fromport,'} ',head,'Callid:',msgd['Call-ID']
    #print msgd
    RESP = head + '\r\n'
    for l in FLDLIST :
        if l in msgd :
            RESP = RESP + l + ': ' + msgd[l] + '\r\n'
    if length > 0 : 
        if 'Event' in msgd :
            RESP = RESP + 'Content-Type: message/sipfrag' + '\r\n'
        else :
            RESP = RESP + 'Content-Type: application/sdp' + '\r\n'
    RESP = RESP + 'Content-Length: {0}\r\n'.format(length)
    RESP = RESP + '\r\n'    # Terminate with empty line
    return RESP+sdp

  def genInvite(self,number,callid) :
    # Generate invite message
    FROMTAG = '1122334455'
    SEQUENCE = 1
    MSGD = {}
    MSGD['User-Agent'] = 'Fortivoice/70D'
    MSGD['From'] =  '<sip:' + number + '@' + self.MYIP + '>' + ";tag={0}".format(FROMTAG)
    MSGD['To'] = '<sip:'+self.NUMBER+'@'+ self.MYIP + '>' 
    MSGD['Via'] = 'SIP/2.0/UDP ' + self.MYIP + ':'+ "{0}".format(self.MYPORT) + ';rport;branch=z9hG4bK-TS-113355'
    MSGD['Contact'] = '<sip:' + number + '@' + self.MYIP + '>'
    MSGD['Call-ID'] = callid
    MSGD['Max-Forwards'] = '70'
    MSGD['CSeq'] = "{0} INVITE".format(SEQUENCE)
    MSGD['Allow'] = self.genAllow()
    return MSGD
#
# Call 
#
class call :
  def __init__(self,callid,netmsg) :
    self.EXT1 = sipext('0000',netmsg)	# Originators extension
    self.EXT2 = sipext('0000',netmsg)	# Terminators extension
    self.EXT3 = sipext('0000',netmsg)	# Transfer extension
    self.CALLID = callid		# Originators callid
    self.NETMSG = netmsg 		# My message handler
    self.CALLSTATE  = 'IDLE'		# Current callstate
    self.RTPPORT = '7050'		# RTP port
    self.RTPPROC = None			# RTP proc
    self.MYIP = netmsg.ipaddr 		# Servers IP
    self.MYPORT = netmsg.port		# Servers Port

  def saveCaller(self,MSGD) :
    # Save caller information
    self.EXT1.SAVEMSG = MSGD

  def saveCalled(self,MSGD) :
    # Save called information
    self.EXT2.SAVEMSG = MSGD

  def callState(self,state) :
      self.CALLSTATE = state

  def refAccept(self,MSGD) :
    # Send accepted to sender
    self.EXT3.sendMsg(MSGD,'SIP/2.0 202 ACCEPTED','')
    self.EXT3.IPADDR = self.NETMSG.fromaddr
    self.EXT3.PORT = self.NETMSG.fromport

  def refNotify(self,MSGD) :
    self.NETMSG.setfrom(self.EXT3.IPADDR,self.EXT3.PORT)
    self.EXT3.sendMsg(MSGD,'NOTIFY sip:'+self.EXT2.NUMBER+'@'+self.MYIP+' SIP/2.0','SIP/2.0 200 OK\r\n\r\n')

  def refCaller(self,MSGD) :
    # Send refer to caller
    self.EXT1.sendRefer(self.EXT3.NUMBER)
    #MSGD = self.EXT1.SAVEMSG
    #MSGD['Contact'] = '<sip:' + self.EXT2.NUMBER + '@' + self.MYIP + '>'
    #MSGD['Refer-To'] = '<sip:'+self.EXT3.NUMBER+'@' + self.MYIP + '>'
    #MSGD['Refered-By'] = '<sip:' + self.EXT2.NUMBER + '@' + self.MYIP + '>'
    #seq = MSGD['CSeq'].split(' ')[0]
    #MSGD['CSeq'] = "{0} REFER".format(int(seq)+1)
    #if self.PARTY == 1 :
    #if True :
    #    MSGD = copy.deepcopy(self.EXT1.SAVEMSG)
    #    to = MSGD['To']
    #    MSGD['To'] = MSGD['From']
    #    MSGD['From'] = to
    #self.NETMSG.setfrom(self.EXT1.IPADDR,self.EXT1.PORT)
    #self.EXT1.sendMsg(MSGD,'REFER sip:'+self.EXT2.NUMBER+'@'+self.MYIP+' SIP/2.0','')

  def refOther(self,MSGD) :
    # Send refer to other
    if self.EXT1.IPADDR == self.NETMSG.fromaddr and self.EXT1.PORT == self.NETMSG.fromport :
        self.EXT2.sendRefer(self.EXT1.NUMBER)
        #MSGD['Contact'] = '<sip:' + self.EXT1.NUMBER + '@' + self.MYIP + '>'
        #self.NETMSG.setfrom(self.EXT2.IPADDR,self.EXT2.PORT)
        #self.EXT1.sendMsg(MSGD,'REFER sip:'+self.EXT1.NUMBER+'@'+self.MYIP+' SIP/2.0','')
    else :
        self.EXT1.sendRefer(self.EXT2.NUMBER)
        #MSGD['Contact'] = '<sip:' + self.EXT2.NUMBER + '@' + self.MYIP + '>'
        #self.NETMSG.setfrom(self.EXT1.IPADDR,self.EXT1.PORT)
        #self.EXT2.sendMsg(MSGD,'REFER sip:'+self.EXT2.NUMBER+'@'+self.MYIP+' SIP/2.0','')

  def ackCalled(self,inc) :
    # Ack the called party
    self.EXT2.sendAck(inc)

  def sendRinging(self,MSGD) :
    # Send ringing to caller
    self.EXT1.sendRinging()

  def sendBusy(self) :
    # Send busy to caller
    self.EXT1.sendBusy()

  def sendDecline(self) :
    # Send decline to caller
    self.EXT1.sendDecline()

  def sendCancel(self) :
    # Cancel the called party
    self.EXT2.sendCancel()

  def sendTrying(self,MSGD) :
    # Send trying to sender 
    self.EXT1.sendTrying(MSGD)

  def sendInvite(self,MSGD) :
    # Send invite to called party
    sdps = MSGD['sdp']
    if self.EXT2.TYPE == '0' :
        self.EXT2.sendInvite(self.EXT1.NUMBER,self.CALLID,sdps)
        self.callState('TRYING')
    if self.EXT2.TYPE == '3' :    # Auto attendant
        self.okAudio(MSGD)
        self.callState('RTPANSWER')

  def okOther(self,MSGD) :
    # Send ok to other party with sdp
    sdps = MSGD['sdp']
    if self.EXT1.IPADDR == self.NETMSG.fromaddr and self.EXT1.PORT == self.NETMSG.fromport :
        self.EXT2.sendOk(sdps)
    else :
        self.EXT1.sendOk(sdps)

  def byeOther(self,MSGD) :
    # Send bye to other party
    if self.EXT1.IPADDR == self.NETMSG.fromaddr and self.EXT1.PORT == self.NETMSG.fromport :
        self.EXT2.sendBye()
    else :
        self.EXT1.sendBye()

  def holdOther(self,MSGD) :
    # Send hold to other party
    sdps = MSGD['sdp']
    if self.EXT1.IPADDR == self.NETMSG.fromaddr and self.EXT1.PORT == self.NETMSG.fromport :
        self.EXT1.SAVEMSG = MSGD	# Save callers invite
        self.EXT2.sendHold(sdps)
    else :
        self.EXT2.SAVEMSG = MSGD	# Save callers invite
        self.EXT1.sendHold(sdps)

  def holdCaller(self,MSGD) :
    # Send hold to calling party
    sdps = MSGD['sdp']
    self.EXT1.sendHold(sdps)
#
# Non session messages
#
  def ackSender(self,MSGD) :
    # Ack the sender
    MSGD['CSeq'] = MSGD['CSeq'].replace('INVITE','ACK')
    self.EXT1.sendMsg(MSGD,'ACK sip:'+MSGD['Fromext']+'@'+self.MYIP+' SIP/2.0','')

  def okSender(self,MSGD) :
    # Send ok to sender
    self.EXT1.sendMsg(MSGD,'SIP/2.0 200 OK','')

  def okOptions(self,MSGD) :
    # Respond to options
    MSGD['Allow'] = self.EXT1.genAllow()
    self.EXT1.sendMsg(MSGD,'SIP/2.0 200 OK','')

  def okSubscribe(self,MSGD) :
    # Respond to subscribe
    MSGD['Expires'] = '3600'
    self.EXT1.sendMsg(MSGD,'SIP/2.0 200 OK','')

#
# Rtp functions
#
  def genSDP(self,myext,myip,myport) :
    # Gen SDP string for audio server
    RESP = 'v=0' + '\r\n'
    RESP = RESP + 'o='+myext+' 123456 654321 IN IP4 '+ myip + '\r\n'
    RESP = RESP + 's=A conversation' + '\r\n'
    RESP = RESP + 'c=IN IP4 ' + myip + '\r\n'
    RESP = RESP + 't=0 0' + '\r\n'
    RESP = RESP + 'm=audio '+myport+' RTP/AVP 0 8 101' + '\r\n'
    RESP = RESP + 'a=rtpmap:0 PCMU/8000/1' + '\r\n'
    RESP = RESP + 'a=rtpmap:8 PCMA/8000/1' + '\r\n'
    RESP = RESP + 'a=rtpmap:101 telephone-event/8000/1' + '\r\n'
    RESP = RESP + 'a=fmtp:101 0-11' + '\r\n'
    return RESP

  def okAudio(self,MSGD) :
    # Send OK for audio
    MSGD['sdp'] = self.genSDP(self.EXT2.NUMBER,self.MYIP,self.RTPPORT)
    self.EXT2.SAVEMSG = MSGD
    sdps = MSGD['sdp']
    MSGD['To'] = MSGD['To'] + ";tag={0}".format('1122334455')
    MSGD['Contact'] = '<sip:' + self.EXT1.NUMBER + '@' + self.MYIP + '>'
    self.EXT1.sendMsg(MSGD,'SIP/2.0 200 OK',sdps)

  def rtpStart(self) :
    # Start RTP
    self.RTPPROC = subprocess.Popen(['/usr/bin/python', './rtpauto.py', self.RTPPORT, self.CALLID, self.EXT2.NUMBER])
    print "Rtp Started Port:",self.RTPPORT,"Callid:",self.CALLID

  def rtpStop(self) :
    # Stop RTP 
    if (self.RTPPROC) :
        print "Rtp Stopped Port:",self.RTPPORT,"Callid:",self.CALLID
        self.RTPPROC.terminate()
    self.RTPPROC = None

  def sendWaiting(self) :
    # Send Waiting to called
    MSGD = self.EXT1.SAVEMSG
    sdps = self.genSDP(self.EXT2.NUMBER,self.MYIP,self.RTPPORT)
    self.RTPPROC = subprocess.Popen(['/usr/bin/python', './rtpauto.py', self.RTPPORT, self.CALLID])
    seq = MSGD['CSeq'].split(' ')[0]
    MSGD['CSeq'] = "{0} INVITE".format(int(seq)+1)
    self.NETMSG.setfrom(self.EXT2.IPADDR,self.EXT2.PORT)
    self.EXT2.sendMsg(MSGD,'INVITE sip:'+self.EXT2.NUMBER+'@'+self.MYIP+' SIP/2.0',sdps)

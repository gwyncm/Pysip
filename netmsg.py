import socket

#
#  Netmsg Class
#
class netmsg :
  def __init__(self, ipaddr,port) :
      self.bufsize = 4096
      self.ipaddr = ipaddr
      self.port = port
      self.fromaddr = ''
      self.fromport = 0
      self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

  def getExternalIP():
      # Can only be used on susyems with a single interface
      sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
      sock.connect(('google.com', 80))
      ip = sock.getsockname()[0]
      sock.close()
      return ip

  def bind(self) :
      self.SOCKET.bind((self.ipaddr,self.port))

  def setfrom(self,fromaddr,fromport) :
      self.fromaddr = fromaddr
      self.fromport = fromport

  def sendmsg(self,msg) :
      self.SOCKET.sendto(msg,(self.fromaddr,self.fromport))

  def recvmsg(self) :
      data,addr = self.SOCKET.recvfrom(self.bufsize)
      self.fromaddr = addr[0]
      self.fromport = addr[1]
      return data

  def close(self) :
      self.SOCKET.close()


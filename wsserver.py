import sys, json

import traceback

from twisted.internet import reactor, ssl
from twisted.python import log
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.static import File

from autobahn.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

class LocalServerProtocol(WebSocketServerProtocol):

   def onConnect(self, *args):
      print "connected", args

   def onMessage(self, msg, binary):
      # unpack
      print "msg", msg, binary
      msg = json.loads(msg)
      id = msg['id']
      command = msg['command']

      def sendResult(res):
          # return result
          print "returning result"
          if len(res) == 1:
              res = res[0]
          data = json.dumps({'id': id, 'result': res})
          self.sendMessage(data, False)

      # call handler
      defer = self.factory._cb(command, msg)

      defer.addCallback(sendResult)

   def doPing(self):
      if self.run:
         self.sendPing()
         self.factory.pingsSent[self.peerstr] += 1
         print self.peerstr, "PING Sent", self.factory.pingsSent[self.peerstr]
         reactor.callLater(1, self.doPing)

   def onPong(self, payload):
      self.factory.pongsReceived[self.peerstr] += 1
      print self.peerstr, "PONG Received", self.factory.pongsReceived[self.peerstr]

   def onOpen(self):
      self.factory.pingsSent[self.peerstr] = 0
      self.factory.pongsReceived[self.peerstr] = 0
      self.run = True
      self.factory.clients.append(self)
      #self.doPing()

   def onClose(self, wasClean, code, reason):
      self.run = False
      self.factory.clients.remove(self)

class LocalServerFactory(WebSocketServerFactory):

   protocol = LocalServerProtocol
   def __init__(self, uri, cb):
      WebSocketServerFactory.__init__(self, uri, debug=False)
      self._cb = cb
      self.pingsSent = {}
      self.pongsReceived = {}
      self.clients = []

   def broadcast(self, cmd, data):
      for client in self.clients:
          try:
              msg = {'command': cmd, 'data': data}
              client.sendMessage(json.dumps(msg), False)
          except:
              traceback.print_exc()

def start_socket(cb):
   log.startLogging(sys.stdout)

   #contextFactory = ssl.DefaultOpenSSLContextFactory('keys/server.key',
   #                                                  'keys/server.crt')

   factory = LocalServerFactory("ws://localhost:9000", cb)
   #factory = LocalServerFactory("wss://localhost:9000",
   #                            debug = 'debug' in sys.argv)

   listenWS(factory)
   #listenWS(factory, contextFactory)

   return factory


if __name__ == '__main__':
   start_socket()
   reactor.run()
   

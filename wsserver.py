import sys, json

from twisted.internet import reactor, ssl
from twisted.python import log
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.static import File

from autobahn.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from autobahn.resource import WebSocketResource

class LocalServerProtocol(WebSocketServerProtocol):

   def onConnect(self, *args):
      print "connected", args

   def onMessage(self, msg, binary):
      print "msg", msg, binary
      res = self.factory._cb(msg, binary)
      print "returning", res
      data = json.dumps({"result": res})
      print "json", data
      self.sendMessage(msg, res)

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
      #self.doPing()

   def onClose(self, wasClean, code, reason):
      self.run = False


class LocalServerFactory(WebSocketServerFactory):

   protocol = LocalServerProtocol
   def __init__(self, uri, cb):
      WebSocketServerFactory.__init__(self, uri, debug=False)
      self._cb = cb
      self.pingsSent = {}
      self.pongsReceived = {}

class RootResource(Resource):
    def __init__(self):
        Resource.__init__(self)

    def getChild(self, name, request):
        return self

    def render_GET(self, request):
        return "Dark Wallet Ghost<br/><b>Dont steal my bitcoins!!</b>"


def start_socket(cb):
   log.startLogging(sys.stdout)

   #contextFactory = ssl.DefaultOpenSSLContextFactory('keys/server.key',
   #                                                  'keys/server.crt')

   #factory = LocalServerFactory("wss://localhost:9000",
   factory = LocalServerFactory("ws://localhost:9000", cb)
   #                            debug = 'debug' in sys.argv)

   #listenWS(factory, contextFactory)
   listenWS(factory)

   resource = WebSocketResource(factory)

   root = RootResource() # File(".")
   root.putChild("ws", resource)
   site = Site(root)

   #reactor.listenSSL(8080, site, contextFactory)
   reactor.listenTCP(50002, site)
   return factory


if __name__ == '__main__':
   start_socket()
   reactor.run()
   

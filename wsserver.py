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
      msg = json.loads(msg)
      id = msg['id']
      command = msg['command']

      def sendResult(res):
          # return result
          if len(res) == 1:
              res = res[0]
          data = json.dumps({'id': id, 'result': res})
          self.sendMessage(data, False)

      # call handler
      defer = self.factory._cb(command, msg)
      defer.addCallback(sendResult)

   def onOpen(self):
      self.run = True
      self.factory.clients.append(self)

   def onClose(self, wasClean, code, reason):
      self.run = False
      self.factory.clients.remove(self)

class LocalServerFactory(WebSocketServerFactory):

   protocol = LocalServerProtocol
   def __init__(self, uri, cb):
      WebSocketServerFactory.__init__(self, uri, debug=False)
      self._cb = cb
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
   

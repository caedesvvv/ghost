#!/usr/bin/env python2
from twisted.internet import gtk2reactor # for gtk-2.0
gtk2reactor.install()

from twisted.internet import reactor
import traceback
import pygtk
pygtk.require('2.0')

import pynotify
import gtk
import os
from time import time
from math import floor
gtk.gdk.threads_init()
import gobject
import wsserver

import obelisk
from obelisk import ObeliskOfLightClient
from zmqproto.zrenode import ZreNode
from twisted.internet.defer import Deferred

#Parameters
MIN_WORK_TIME = 60 * 10 # min work time in seconds
ENABLE_ZRE = True

class DesktopGhost(ObeliskOfLightClient):
    def __init__(self, *addresses):
        ObeliskOfLightClient.__init__(self, *addresses)
        self.icon=gtk.status_icon_new_from_file(self.icon_path("walletlogo.png"))
        self.icon.set_tooltip("Idle")
        self.state = "idle"
        self.tick_interval=10 #number of seconds between each poll
        self.icon.connect('activate',self.icon_click)
        self.icon.set_visible(True)
        self.start_working_time = 0
        pynotify.init("DarkWallet Ghost")
        self._last_height = 0
        #self.fetch_last_height(self._on_last_height_fetched)
        self.ws = wsserver.start_socket(self._on_websocket_msg)
        self.peers = []
        if ENABLE_ZRE:
            self.zre = ZreNode('', self._on_zre_beacon)

    def _on_zre_beacon(self, uuid):
        """ZRE beacon arrived"""
        self.send_notification("DarkWallet", "Found peer %s" %uuid)
        self.peers.append(uuid)

    def _on_websocket_msg(self, command, data):
        """websocket message arrived"""
        defer = Deferred()
        def trigger_defer(*args):
            print "trigger defer", args
            if args[0]:
                defer.errback(args[0])
            else:
                defer.callback(args[1:])
        if command == "fetch_last_height":
            self.send_notification("DarkWallet", "Connected!")
            self.fetch_last_height(trigger_defer)
        elif command == "fetch_history":
            address = data['data']['address']
            def format_history(*args):
                args = list(args)
                for idx, arg in enumerate(args):
                    if arg.__class__ == str:
                        args[idx] = arg.encode('hex')
                    if arg.__class__ in [tuple, list]:
                        args[idx] = format_history(*arg)
                return args
            defer.addCallback(format_history)
            self.fetch_history(address, trigger_defer)
        elif command == "subscribe_address":
            address = data['data']['address']
            self.subscribe_address(address, self.address_update, trigger_defer)
        return defer

    def address_update(self, address_version, address_hash, height, block_hash, tx):
        """address update arrived (from address_subscribe)"""
        msg = {
            'address_version': address_version,
            'address_hash': address_hash.encode('hex'),
            'height': height,
            'block_hash': block_hash.encode('hex'),
            'tx': tx.encode('hex')
        }
        self.ws.broadcast('address', msg)

    def _on_last_height_fetched(self, ec, height, tx_hashes=[]):
        """last height arrived"""
        if self._last_height != height:
            self.send_notification("New Block", "height %s: %s transactions" %(height, len(tx_hashes)))
            self.icon.set_tooltip("Last height: " + str(height))
            self._last_height = height
        #reactor.callLater(1, self.fetch_last_height, self._on_last_height_fetched)

    def send_notification(self, title, message):
        """send a notification to the desktop"""
        try:
            n = pynotify.Notification(title, message)
            n.set_icon_from_pixbuf(self.icon.get_pixbuf())
            n.show()
        except:
            traceback.print_exc()

    def format_time(self,seconds):
        minutes = floor(seconds / 60)
        if minutes > 1:
            return "%d minutes" % minutes
        else:
            return "%d minute" % minutes

    def set_state(self,state):
        """set icon state"""
        old_state=self.state
        self.icon.set_from_file(self.icon_path(state+".png"))
        if state == "idle":
            delta = time() - self.start_working_time
            if old_state == "ok":
                self.icon.set_tooltip("Good! Worked for %s." % 
                        self.format_time(delta))
            elif old_state == "working":
                self.icon.set_tooltip("Not good: worked for only %s." % 
                        self.format_time(delta))
        else:
            if state == "working":
                self.start_working_time = time()
            delta = time() - self.start_working_time
            self.icon.set_tooltip("Working for %s..." % self.format_time(delta))
        self.state=state

    def icon_path(self, icon):
        return os.path.join(self.icon_directory(), 'images', icon)

    def icon_directory(self):
        return os.path.dirname(os.path.realpath(__file__)) + os.path.sep

    def icon_click(self,dummy):
        delta = time() - self.start_working_time
        if self.state == "idle":
            self.set_state("working")
        else:
            self.set_state("idle")

    def update(self):
        """This method is called everytime a tick interval occurs"""
        delta = time() - self.start_working_time
        if self.state == "idle":
            pass
        else:
            self.icon.set_tooltip("Working for %s..." % self.format_time(delta))
            if self.state == "working":
                if delta > MIN_WORK_TIME:
                    self.set_state("ok")
        source_id = gobject.timeout_add(self.tick_interval*1000, self.update)
    def main(self):
        # All PyGTK applications must have a gtk.main(). Control ends here
        # and waits for an event to occur (like a key press or mouse event).
        source_id = gobject.timeout_add(self.tick_interval, self.update)
        gtk.main()

    # PubSub Callbacks
    def on_raw_block(self, height, hash, header, tx_num, tx_hashes):
        print "* block", height, len(tx_hashes)
        print obelisk.serialize.deser_block_header(header)

        self._on_last_height_fetched(None, height, tx_hashes)
        msg = {'height': height,
               'hash': hash.encode('hex'),
               'header': header.encode('hex'),
               'tx_num': tx_num.encode('hex'),
               'tx_hashes': map(lambda s: s.encode('hex'), tx_hashes)
        }
        self.ws.broadcast('block', msg)

    def on_raw_transaction(self, hash, transaction):
        tx = obelisk.serialize.deser_tx(transaction)
        outputs = []
        for output in tx.outputs:
            outputs.append(obelisk.util.format_satoshis(output.value))
        #print "* tx", hash.encode('hex'), ", ".join(outputs), "(%.2fkB)"%(len(transaction)/1024,)
        self.icon_click('')
 
# If the program is run directly or passed as an argument to the python
# interpreter then create a Widget instance and show it
if __name__ == "__main__":
    app = DesktopGhost('tcp://85.25.198.97:8081', 'tcp://85.25.198.97:8083', 'tcp://85.25.198.97:8084')
    app.main()

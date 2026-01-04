from pox.core import core
import pox.openflow.libopenflow_01 as of
import threading
import zmq
import os
import struct

log = core.getLogger()

class SDRQoSController(object):
    def __init__(self):
        self.mac_to_port = {}
        self.last_rate = 0 
        core.openflow.addListeners(self)
        
        self.zmq_thread = threading.Thread(target=self.zmq_listener, daemon=True)
        self.zmq_thread.start()
        
        log.info("=== Controller Ready: Waiting for GRC (Multipart Binary) ===")

    def parse_zmq_message(self, parts):
        # 1. Validation: Must be multipart [Topic, Data]
        if len(parts) != 2:
            return None

        topic, data = parts
        
        # 2. Validation: Topic must match
        if topic != b'BITRATE':
            return None

        # 3. Validation: Data must be at least 4 bytes (one float)
        if len(data) < 4:
            return None

        try:
            # 4. Parsing: Unpack first 4 bytes as Little Endian Float
            # We ignore extra bytes if GRC sends a large buffer
            bitrate = struct.unpack('<f', data[:4])[0]
            return bitrate
        except struct.error:
            return None

    def zmq_listener(self):
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.connect("tcp://127.0.0.1:5555")
        socket.setsockopt(zmq.SUBSCRIBE, b"BITRATE")
        
        while True:
            try:
                # Use recv_multipart to receive [Topic, Data] envelopes together
                parts = socket.recv_multipart()
                
                # Delegate parsing to helper function
                bitrate = self.parse_zmq_message(parts)
                
                # Only proceed if parsing was successful
                if bitrate is not None:
                    self.enforce_qos(bitrate)
                        
            except Exception:
                pass

    def enforce_qos(self, bitrate):
        rate_kbps = int(bitrate / 1000)
        
        if rate_kbps < 1: rate_kbps = 1
        
        # Anti-Thrashing
        if rate_kbps == self.last_rate: return

        # Burst Optimization: burst = rate for video stability
        burst = rate_kbps 
        if burst < 2000: burst = 2000 

        os.system(f"ovs-vsctl set interface s1-eth1 ingress_policing_rate={rate_kbps}")
        os.system(f"ovs-vsctl set interface s1-eth1 ingress_policing_burst={burst}")
        
        log.info(f"*** QoS UPDATE: Rate={rate_kbps} kbps ***")
        self.last_rate = rate_kbps

    def _handle_PacketIn(self, event):
        try:
            packet = event.parsed
            if not packet or not packet.parsed: return
        except Exception:
            return
            
        dpid = event.dpid
        inport = event.port
        
        if dpid not in self.mac_to_port: self.mac_to_port[dpid] = {}
        self.mac_to_port[dpid][packet.src] = inport
        
        if packet.dst in self.mac_to_port[dpid]:
            outport = self.mac_to_port[dpid][packet.dst]
        else:
            outport = of.OFPP_FLOOD
            
        if outport != of.OFPP_FLOOD:
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match(dl_src=packet.src, dl_dst=packet.dst)
            msg.idle_timeout = 0
            msg.hard_timeout = 0
            msg.actions.append(of.ofp_action_output(port=outport))
            event.connection.send(msg)

        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=outport))
        msg.in_port = inport
        event.connection.send(msg)

def launch():
    core.registerNew(SDRQoSController)
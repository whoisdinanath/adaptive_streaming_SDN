import eventlet
eventlet.monkey_patch()
import zmq
import os
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet
from os_ken.lib import hub

class SDRQoSOrchestrator(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    def __init__(self, *args, **kwargs):
        super(SDRQoSOrchestrator, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.zmq_ctx = zmq.Context()
        # Use OS-Ken native hub instead of threading
        hub.spawn(self.zmq_listener)
    
    def zmq_listener(self):
        socket = self.zmq_ctx.socket(zmq.SUB)
        socket.connect("tcp://127.0.0.1:5555")
        socket.setsockopt_string(zmq.SUBSCRIBE, "BITRATE")
        self.logger.info("ZeroMQ listener started, waiting for bitrate messages...")
        
        while True:
            try:
                msg = socket.recv_string()
                topic, bitrate_str = msg.split()
                bitrate = float(bitrate_str)
                self.enforce_qos(bitrate)
            except Exception as e:
                self.logger.error(f"ZMQ Error: {e}")
            hub.sleep(0.1)  # Yield to other green threads
    
    def enforce_qos(self, bitrate):
        rate_kbps = int(bitrate / 1000)
        burst = int(rate_kbps / 10)
        self.logger.info(f"SDR Telemetry -> Rate: {rate_kbps}kbps, Burst: {burst}kb")
        # OVS commands to enforce physical layer constraints on the data plane
        os.system(f"ovs-vsctl set interface s1-eth2 ingress_policing_rate={rate_kbps}")
        os.system(f"ovs-vsctl set interface s1-eth2 ingress_policing_burst={burst}")
    
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                         ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Switch connected - table-miss flow installed")
    
    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                               match=match, instructions=inst)
        datapath.send_msg(mod)
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        
        self.mac_to_port.setdefault(dpid, {})
        
        # Learn MAC address to avoid future packet_ins
        self.mac_to_port[dpid][src] = in_port
        
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD
        
        actions = [parser.OFPActionOutput(out_port)]
        
        # If we know the port, install a flow to stay in the data plane
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)
            self.logger.info(f"Flow installed: {src} -> {dst} via port {out_port}")
        
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                 in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
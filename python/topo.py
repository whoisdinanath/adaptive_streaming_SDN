from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def network_topology():
    # Use OVSKernelSwitch to ensure we can use ovs-ofctl commands
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    
    info('*** Adding controller\n')
    # OS-Ken/Ryu usually listens on 6653
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Adding switches\n')
    # CRITICAL: Specify OpenFlow13 here
    s1 = net.addSwitch('s1', protocols='OpenFlow10')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')

    info('*** Creating links\n')
    net.addLink(h1, s1)
    net.addLink(h2, s1)

    info('*** Starting network\n')
    net.start()
    
    # This keeps the network alive so you can run dump-flows
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    network_topology()
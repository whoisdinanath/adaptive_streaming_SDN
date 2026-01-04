import org.zeromq.SocketType;
import org.zeromq.ZMQ;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.ExecutionException;
import java.util.logging.Level;
import java.util.logging.Logger;

// OpenDaylight OVSDB imports (commented out for standalone mode)
/*
import org.opendaylight.controller.md.sal.binding.api.DataBroker;
import org.opendaylight.controller.md.sal.binding.api.ReadWriteTransaction;
import org.opendaylight.controller.md.sal.common.api.data.LogicalDatastoreType;
import org.opendaylight.yang.gen.v1.urn.opendaylight.params.xml.ns.yang.ovsdb.rev150105.OvsdbTerminationPointAugmentation;
import org.opendaylight.yang.gen.v1.urn.opendaylight.params.xml.ns.yang.ovsdb.rev150105.OvsdbTerminationPointAugmentationBuilder;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.NetworkTopology;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.TopologyId;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.NodeId;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.TpId;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.Topology;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.TopologyKey;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.topology.Node;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.topology.NodeKey;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.topology.node.TerminationPoint;
import org.opendaylight.yang.gen.v1.urn.tbd.params.xml.ns.yang.network.topology.rev131021.network.topology.topology.node.TerminationPointKey;
import org.opendaylight.yangtools.yang.binding.InstanceIdentifier;
*/

/**
 * SDN Controller for Adaptive Bitrate Streaming with QoS Control.
 * 
 * This controller listens for bitrate updates from a GNU Radio Companion (GRC)
 * flowgraph via ZeroMQ and dynamically adjusts OVS QoS settings.
 * 
 * Standalone mode: Uses direct ovs-vsctl commands (like Python version)
 * OpenDaylight mode: Uses OVSDB southbound plugin (uncomment ODL imports)
 */
public class SDRListener implements Runnable {

    private static final Logger LOG = Logger.getLogger(SDRListener.class.getName());

    // ZeroMQ configuration
    private static final String ZMQ_ADDRESS = "tcp://127.0.0.1:5555";
    private static final String ZMQ_TOPIC = "BITRATE";

    // OVS configuration
    private static final String OVS_INTERFACE = "s1-eth1";

    private final ZMQ.Context context;
    private final ZMQ.Socket subscriber;
    private final boolean useOvsctl; // true = direct ovs-vsctl, false = OVSDB

    private long lastRateKbps = 0;
    private volatile boolean running = true;

    /**
     * Constructor for standalone mode (using ovs-vsctl).
     */
    public SDRListener() {
        this(true);
    }

    /**
     * Constructor with mode selection.
     * 
     * @param useOvsctl true to use direct ovs-vsctl commands, false for OVSDB
     */
    public SDRListener(boolean useOvsctl) {
        this.useOvsctl = useOvsctl;
        this.context = ZMQ.context(1);
        this.subscriber = context.socket(SocketType.SUB);
    }

    /**
     * Main run loop - listens for ZMQ messages and updates QoS accordingly.
     */
    @Override
    public void run() {
        try {
            subscriber.connect(ZMQ_ADDRESS);
            subscriber.subscribe(ZMQ_TOPIC.getBytes());
            LOG.info("=== SDR Controller Ready: Listening on " + ZMQ_ADDRESS + " ===");
            LOG.info("Mode: " + (useOvsctl ? "Direct ovs-vsctl" : "OVSDB"));

            while (running && !Thread.currentThread().isInterrupted()) {
                // Receive multipart message [Topic, Data]
                byte[] topic = subscriber.recv(0);
                if (topic == null) {
                    continue;
                }

                byte[] data = subscriber.recv(0);
                if (data == null || data.length < 4) {
                    LOG.warning("Received invalid data packet");
                    continue;
                }

                // Parse bitrate as little-endian float (matching GRC output)
                float bitrate = ByteBuffer.wrap(data)
                        .order(ByteOrder.LITTLE_ENDIAN)
                        .getFloat();

                if (Float.isNaN(bitrate) || Float.isInfinite(bitrate) || bitrate < 0) {
                    LOG.warning("Received invalid bitrate value: " + bitrate);
                    continue;
                }

                updateQos(bitrate);
            }
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in SDR listener loop", e);
        } finally {
            cleanup();
        }
    }

    /**
     * Updates QoS settings based on the received bitrate.
     * 
     * @param bitrate The bitrate in bps received from GRC
     */
    private void updateQos(float bitrate) {
        // Convert bps to kbps
        long rateKbps = (long) (bitrate / 1000);
        if (rateKbps < 1) {
            rateKbps = 1;
        }

        // Anti-thrashing: skip if rate hasn't changed
        if (rateKbps == lastRateKbps) {
            return;
        }

        // Calculate burst size (minimum 2000 kbps for video stability)
        long burstKbps = Math.max(rateKbps, 2000L);

        if (useOvsctl) {
            updateQosViaOvsctl(rateKbps, burstKbps);
        } else {
            // For OVSDB mode, you would need DataBroker injected
            LOG.warning("OVSDB mode not implemented in standalone mode");
        }

        lastRateKbps = rateKbps;
    }

    /**
     * Updates QoS using direct ovs-vsctl commands (like Python controller).
     * 
     * @param rateKbps The ingress policing rate in kbps
     * @param burstKbps The ingress policing burst in kbps
     */
    private void updateQosViaOvsctl(long rateKbps, long burstKbps) {
        try {
            // Set ingress policing rate
            ProcessBuilder pb1 = new ProcessBuilder(
                "ovs-vsctl", "set", "interface", OVS_INTERFACE,
                "ingress_policing_rate=" + rateKbps
            );
            Process p1 = pb1.start();
            int exit1 = p1.waitFor();

            // Set ingress policing burst
            ProcessBuilder pb2 = new ProcessBuilder(
                "ovs-vsctl", "set", "interface", OVS_INTERFACE,
                "ingress_policing_burst=" + burstKbps
            );
            Process p2 = pb2.start();
            int exit2 = p2.waitFor();

            if (exit1 == 0 && exit2 == 0) {
                LOG.info(String.format("*** QoS UPDATE: Rate=%d kbps, Burst=%d kbps ***", 
                        rateKbps, burstKbps));
            } else {
                LOG.warning("Failed to execute ovs-vsctl commands");
            }

        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Failed to update QoS via ovs-vsctl", e);
        }
    }

    /**
     * Stops the listener gracefully.
     */
    public void stop() {
        running = false;
    }

    /**
     * Cleans up ZeroMQ resources.
     */
    private void cleanup() {
        LOG.info("Shutting down SDR listener...");
        if (subscriber != null) {
            subscriber.close();
        }
        if (context != null) {
            context.term();
        }
    }

    /**
     * Main method for standalone execution.
     */
    public static void main(String[] args) {
        LOG.info("Starting SDR Listener (Java version)...");
        
        SDRListener listener = new SDRListener(true); // Use ovs-vsctl mode
        Thread listenerThread = new Thread(listener);
        listenerThread.start();

        // Add shutdown hook for graceful termination
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            LOG.info("Shutdown signal received...");
            listener.stop();
            try {
                listenerThread.join(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }));
    }
}

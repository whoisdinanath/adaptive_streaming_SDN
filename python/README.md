# SDR Adaptive Streaming - Python Controllers

Python implementations of SDN controllers for adaptive bitrate streaming with QoS control.

## Files

- **pox_controller.py** - POX-based SDN controller with ZMQ listener and QoS enforcement
- **qos_app.py** - Alternative QoS application implementation
- **topo.py** - Network topology definition for Mininet
- **listen.py** - ZMQ listener utility
- **trans.py** - Transmission utility

## Prerequisites

```bash
pip install pyzmq
```

For POX controller:

```bash
git clone https://github.com/noxrepo/pox.git
cd pox
```

## Running POX Controller

```bash
# From POX directory
./pox.py log.level --DEBUG /path/to/pox_controller

# Or copy controller to POX ext directory
cp pox_controller.py /path/to/pox/ext/
./pox.py log.level --DEBUG pox_controller
```

## How It Works

1. Listens on ZeroMQ `tcp://127.0.0.1:5555` for "BITRATE" topic
2. Receives multipart messages: [Topic, Data]
3. Parses little-endian float bitrate from GRC
4. Updates OVS QoS via `ovs-vsctl` commands
5. Handles OpenFlow packet-in events for L2 switching

## Testing

```python
# Test ZMQ connection
python listen.py

# Start network topology
sudo python topo.py
```

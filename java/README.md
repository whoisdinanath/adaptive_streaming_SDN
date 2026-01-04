# SDR Adaptive Streaming Controller - Java Version

Java implementation of the SDN controller for adaptive bitrate streaming with QoS control.

## Directory Structure

```
java/
├── pom.xml                    # Maven build configuration
└── src/main/java/
    └── SDRListener.java       # Main controller implementation
```

## Prerequisites

- Java 11 or higher
- Maven 3.6+
- Open vSwitch configured with interface `s1-eth1`
- GNU Radio flowgraph sending bitrate updates via ZeroMQ

## Building

```bash
cd java
mvn clean package
```

This creates:

- `target/sdr-controller-1.0-SNAPSHOT.jar` - Fat JAR with all dependencies

## Running

### Option 1: Using Maven

```bash
cd java
mvn compile exec:java
```

### Option 2: Using the JAR

```bash
cd java
java -jar target/sdr-controller-1.0-SNAPSHOT.jar
```

### Option 3: With custom Java options

```bash
cd java
java -Xmx512m -jar target/sdr-controller-1.0-SNAPSHOT.jar
```

## How It Works

1. **Listens** for ZeroMQ messages on `tcp://127.0.0.1:5555`
2. **Subscribes** to the "BITRATE" topic
3. **Parses** little-endian float bitrate values from GRC
4. **Updates** OVS QoS settings using `ovs-vsctl` commands:
   - `ingress_policing_rate` = bitrate in kbps
   - `ingress_policing_burst` = max(bitrate, 2000) kbps

## Configuration

Edit these constants in `SDRListener.java`:

```java
private static final String ZMQ_ADDRESS = "tcp://127.0.0.1:5555";
private static final String ZMQ_TOPIC = "BITRATE";
private static final String OVS_INTERFACE = "s1-eth1";
```

## Stopping

Press `Ctrl+C` - the controller will shut down gracefully.

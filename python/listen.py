import zmq
import struct
import binascii
import time

def listen_to_port():
    print("=== ZMQ Sniffer for Port 5555 ===")
    
    # 1. Setup ZMQ Context
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    
    # 2. Connect (The 'Sink' binds, so we must connect)
    target = "tcp://127.0.0.1:5555"
    print(f"Attempting to connect to {target}...")
    try:
        socket.connect(target)
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    # 3. Subscribe to EVERYTHING
    # If we don't do this, the socket filters out all messages by default
    socket.setsockopt(zmq.SUBSCRIBE, b"")
    
    print("Connected! Waiting for data streams...")
    print("-" * 50)

    while True:
        try:
            # 4. Receive Data (Blocking wait)
            data = socket.recv()
            
            # 5. Decode Logic
            # Convert binary to hex string for debugging
            hex_data = binascii.hexlify(data).decode('utf-8')
            
            # Try to interpret as a Float (Standard for GNU Radio)
            # '<f' = Little Endian Float (4 bytes)
            decoded_val = "???"
            if len(data) == 4:
                decoded_val = f"{struct.unpack('<f', data)[0]:.2f}"
            
            # 6. Print clearly
            print(f"RECEIVED | Length: {len(data)} bytes | Hex: [0x{hex_data}] | Float Value: {decoded_val}")
            
        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"\nError receiving: {e}")

if __name__ == "__main__":
    listen_to_port()
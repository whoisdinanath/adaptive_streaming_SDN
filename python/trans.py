import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5555")

print("Fake SDR transmitting...")

while True:
    # Send 500 Mbps (Good for Video)
    msg = "BITRATE 500000000"
    socket.send_string(msg)
    print(f"Sent: {msg}")
    time.sleep(2)
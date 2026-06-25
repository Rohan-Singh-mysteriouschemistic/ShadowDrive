import socket
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('127.0.0.1', 5432))
    # send a startup message to see if we get a response
    s.send(b'\x00\x00\x00\x08\x04\xd2\x16\x2f') # Cancel request or SSL request
    print("Sent. Waiting for response...")
    data = s.recv(1024)
    print("Received:", data)
except Exception as e:
    print("Error:", e)

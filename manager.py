import sys
import socket
 
PORT = 0  # Treating as constant, set by args
BUFFER_SIZE = 1024

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # IPv4, UDP
peers = {} # name -> ip, m-port, p-port

def main():

    # Check args
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <port>")
        sys.exit(1)
 
    PORT = int(sys.argv[1])

    if(PORT < 33000 or PORT > 33499): # specified port range for group 64
        print("Error: Port number must be between 33000 and 33499")
        sys.exit(1)
    
    sock.bind(("", PORT))

    # Main loop
    while(True):
        data, addr = sock.recvfrom(BUFFER_SIZE)
        print(f"Received message from {addr}: {data.decode()}")

        args = data.decode().split()
        command = args[0]

        # call correct handler
        match(command):
            case "register":
                handle_register(args, addr)
            case "setup-dht":
                handle_setup-dht(args, addr)
            case "dht-complete":
                handle_dht-complete(args, addr)
            case "query-dht":
                handle_query-dht(args, addr)
            case "leave-dht":
                handle_leave-dht(args, addr)
            case "join-dht":
                handle_join-dht(args, addr)
            case "dht-rebuilt":
                handle_dht-rebuilt(args, addr)
            case "deregister":
                handle_deregister(args, addr)
            case "teardown-dht":
                handle_teardown-dht(args, addr)
            case "teardown-complete":
                handle_teardown-complete(args, addr)
            case _:
                print(f"Warning: Unknown command: {command}")

def handle_register(args, addr):
    
    # Validate args
    if len(args) != 5:
        print(f"Error: Invalid number of args. Usage: register ⟨peer-name⟩ ⟨IPv4-address⟩ ⟨m-port⟩ ⟨p-port⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if (not (args[1].isalpha() and len(args[1]) <= 15)):
        print(f"Error: Invalid peer name: {args[1]}. Must be alphabetic and at most 15 characters.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(args[1] in peers):
        print(f"Error: Peer name already registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(any(peer["ip"] == args[2] and peer["m-port"] in (args[3], args[4]) or peer["p-port"] in (args[3], args[4]) for peer in peers.values())): # if ip matches, ports must be new
        print(f"Error: for given IP, at least one port already registered: {args[3]} and {args[4]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Register peer
    peers[args[1]] = {"ip": args[2], "m-port": args[3], "p-port": args[4]}
    print(f"Registered peer: {args[1]} with IP {args[2]}, m-port {args[3]}, p-port {args[4]}")
    sock.sendto("SUCCESS".encode(), addr)

def handle_setup-dht(args, addr):

def handle_dht-complete(args, addr):

def handle_query-dht(args, addr):

def handle_leave-dht(args, addr):

def handle_join-dht(args, addr):

def handle_dht-rebuilt(args, addr):

def handle_deregister(args, addr):

def handle_teardown-dht(args, addr):

def handle_teardown-complete(args, addr):
 
if __name__ == "__main__":
    main()
 
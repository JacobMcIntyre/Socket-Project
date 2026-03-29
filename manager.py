import sys
import socket
from enum import Enum
import random

class PeerState(Enum):
    FREE = 0
    LEADER = 1
    INDHT = 2

class ListenerState(Enum):
    NONE = 0
    DHT_COMPLETE = 1
    DHT_REBUILT = 2
    TEARDOWN_COMPLETE = 3

PORT = 0  # Treating as constant, set by args
BUFFER_SIZE = 1024

dht_exists = False
listening_for = ListenerState.NONE
peer_leaving_or_joining = None

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # IPv4, UDP
peers = {} # name -> ip, m-port, p-port, state

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
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_register(args, addr)
            case "setup-dht":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_setup_dht(args, addr)
            case "dht-complete":
                if(listening_for != ListenerState.DHT_COMPLETE):
                    print(f"Error: Not listening for dht-complete. This command can only be processed after setup-dht.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_dht_complete(args, addr)
            case "query-dht":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_query_dht(args, addr)
            case "leave-dht":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_leave_dht(args, addr)
            case "join-dht":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_join_dht(args, addr)
            case "dht-rebuilt":
                if(listening_for != ListenerState.DHT_REBUILT):
                    print(f"Error: Not listening for dht-rebuilt. This command can only be processed after leave or join dht.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_dht_rebuilt(args, addr)
            case "deregister":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_deregister(args, addr)
            case "teardown-dht":
                if(listening_for != ListenerState.NONE):
                    print(f"Error: Currently listening. Cannot process other commands until done.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_teardown_dht(args, addr)
            case "teardown-complete":
                if(listening_for != ListenerState.TEARDOWN_COMPLETE):
                    print(f"Error: Not listening for teardown-complete. This command can only be processed after teardown-dht.")
                    sock.sendto("FAILURE".encode(), addr)
                else:
                    handle_teardown_complete(args, addr)
            case _:
                print(f"Error: Unknown command: {command}")
                sock.sendto("FAILURE".encode(), addr)

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
    peers[args[1]] = {"ip": args[2], "m-port": args[3], "p-port": args[4], "state": PeerState.FREE}
    print(f"Registered peer: {args[1]} with IP {args[2]}, m-port {args[3]}, p-port {args[4]}, state FREE")
    sock.sendto("SUCCESS".encode(), addr)

def handle_setup_dht(args, addr):
    # Validate args
    if len(args) != 4:
        print(f"Error: Invalid number of args. Usage: setup-dht ⟨peer-name⟩ ⟨n⟩ ⟨YYYY⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[2] < 3:
        print(f"Error: N must be at least 3: {args[2]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(len(peers) < args[2]):
        print(f"Error: Not enough registered peers to set up DHT. Registered peers: {len(peers)}, N: {args[2]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(dht_exists):
        print(f"Error: DHT already exists. Cannot set up another DHT until current one is torn down.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    peers[args[1]]["state"] = PeerState.LEADER

    # Choose peers and format message
    free_peers = [peer for peer in peers if peers[peer]["state"] == PeerState.FREE]
    chosen_peers = random.sample(free_peers, args[2] - 1)
    chosen_peers_str = " ".join(f"{p} {peers[p]['ip']} {peers[p]['p-port']}" for p in chosen_peers)
    message = f"SUCCESS {args[1]} {peers[args[1]]['ip']} {peers[args[1]]['p-port']} {chosen_peers_str}" 

    # wait for dht complete
    listening_for = ListenerState.DHT_COMPLETE
    dht_exists = True
    print(f"Peer {args[1]} initiated set up DHT and is now LEADER, waiting for completion")
    sock.sendto(message.encode(), addr)

def handle_dht_complete(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: dht-complete ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] != PeerState.LEADER:
        print(f"Error: Peer {args[1]} is not the LEADER and cannot complete DHT setup.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # dht setup complete
    listening_for = ListenerState.NONE
    print(f"DHT setup complete.")
    sock.sendto("SUCCESS".encode(), addr)

def handle_query_dht(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: query-dht ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(not dht_exists):
        print(f"Error: DHT does not exist. Cannot query DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(peers[args[1]]["state"] != PeerState.FREE):
        print(f"Error: Peer {args[1]} is not in DHT and cannot query DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Query dht response
    peers_in_dht = [peer for peer in peers if peers[peer]["state"] in (PeerState.LEADER, PeerState.INDHT)]
    random_peer = random.choice(peers_in_dht)
    print(f"Peer {args[1]} queried DHT. Responding with peer {random_peer} with ip {peers[random_peer]['ip']}, p-port {peers[random_peer]['p-port']}")
    sock.sendto(f"SUCCESS {random_peer} {peers[random_peer]['ip']} {peers[random_peer]['p-port']}".encode(), addr)
        
def handle_leave_dht(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: leave-dht ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(not dht_exists):
        print(f"Error: DHT does not exist. Cannot leave DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] not in (PeerState.LEADER, PeerState.INDHT):
        print(f"Error: Peer {args[1]} is not in DHT and cannot leave DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Leave dht recorded
    listening_for = ListenerState.DHT_REBUILT
    peer_leaving_or_joining = args[1]
    print(f"Peer {args[1]} is leaving DHT. Waiting for DHT to be rebuilt.")
    sock.sendto("SUCCESS".encode(), addr)

def handle_join_dht(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: join-dht ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(not dht_exists):
        print(f"Error: DHT does not exist. Cannot join DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] != PeerState.FREE:
        print(f"Error: Peer {args[1]} is not FREE and cannot join DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Join dht recorded
    listening_for = ListenerState.DHT_REBUILT
    peer_leaving_or_joining = args[1]
    print(f"Peer {args[1]} is joining DHT. Waiting for DHT to be rebuilt.")
    sock.sendto("SUCCESS".encode(), addr)

def handle_dht_rebuilt(args, addr):
    # Validate args
    if len(args) != 3:
        print(f"Error: Invalid number of args. Usage: dht-rebuilt ⟨peer-name⟩ ⟨new-leader⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] != peer_leaving_or_joining:
        print(f"Error: Peer is different than peer leaving/joining: {args[1]} given, {peer_leaving_or_joining} expected")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[2] not in peers:
        print(f"Error: New leader {args[2]} is not registered.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[2]]["state"] not in (PeerState.LEADER, PeerState.INDHT) and args[2] != peer_leaving_or_joining: # if new leader is not already in dht, must be peer joining
        print(f"Error: New leader {args[2]} is not in DHT and is not the peer joining DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Remove/add given peer
    if(peers[args[1]]["state"] == PeerState.FREE):
        peers[args[1]]["state"] = PeerState.INDHT
    else:
        peers[args[1]]["state"] = PeerState.FREE

    # Replace leader
    for peer in peers:
        if peers[peer]["state"] == PeerState.LEADER:
            peers[peer]["state"] = PeerState.INDHT
    peers[args[2]]["state"] = PeerState.LEADER

    #rebuild complete
    listening_for = ListenerState.NONE
    peer_leaving_or_joining = None
    print(f"DHT rebuilt complete.")
    sock.sendto("SUCCESS".encode(), addr)

def handle_deregister(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: deregister ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] != PeerState.FREE:
        print(f"Error: Peer {args[1]} is currently in DHT and cannot deregister.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # Deregister peer
    del peers[args[1]]
    print(f"Deregistered peer: {args[1]}")
    sock.sendto("SUCCESS".encode(), addr)

def handle_teardown_dht(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: teardown-dht ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if(not dht_exists):
        print(f"Error: DHT does not exist. Cannot tear down DHT.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] != PeerState.LEADER:
        print(f"Error: Peer {args[1]} is not the LEADER and cannot initiate DHT teardown.")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    # wait for teardown complete
    listening_for = ListenerState.TEARDOWN_COMPLETE
    print(f"Peer {args[1]} initiated tear down of DHT and is LEADER, waiting for completion")
    sock.sendto("SUCCESS".encode(), addr)

def handle_teardown_complete(args, addr):
    # Validate args
    if len(args) != 2:
        print(f"Error: Invalid number of args. Usage: teardown-complete ⟨peer-name⟩")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if args[1] not in peers:
        print(f"Error: Peer name not registered: {args[1]}")
        sock.sendto("FAILURE".encode(), addr)
        return
    
    if peers[args[1]]["state"] != PeerState.LEADER:
        print(f"Error: Peer {args[1]} is not the LEADER and cannot complete DHT teardown.")
        sock.sendto("FAILURE".encode(), addr)
        return

    # Complete DHT teardown
    dht_exists = False
    for peer in peers:
        peers[peer]["state"] = PeerState.FREE
    print(f"DHT teardown complete.")
    sock.sendto("SUCCESS".encode(), addr)

if __name__ == "__main__":
    main()
 

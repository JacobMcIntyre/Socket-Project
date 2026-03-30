import sys
import socket
import random
import threading
import csv
import time
import os
 
MANAGER_IP = "null"  # Treating as constants, set by args
MANAGER_PORT = 0
BUFFER_SIZE = 65535

local_name = "null"
ip = "null"
p_port = 0
m_port = 0
id = 0

ring_size = 0
s = 0 # Size of hash space
year = 0

p_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
m_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dht_slice = {} #event_id -> state, year, month_name, event_type, cz_type, cz_name, injuries_direct, injuries_indirect, deaths_direct, deaths_indirect, damage_property, damage_crops, tor_f_scale

peers = []
next_peer = None

def main():
    global MANAGER_IP, MANAGER_PORT, local_name, ip, p_port, m_port

    # Check args
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <manager_ip> <manager_port>")
        sys.exit(1)
 
    MANAGER_IP = sys.argv[1]
    MANAGER_PORT = int(sys.argv[2])

    if(MANAGER_PORT < 33000 or MANAGER_PORT > 33499):
        print("Error: Port number must be between 33000 and 33499")
        sys.exit(1)


    m_port = set_port("m")
    print(f"Manager socket assigned to port {m_port}")

    p_port = set_port("p")
    print(f"Peer socket assigned to port {p_port}")

    ip = socket.gethostbyname(socket.gethostname())
    print(f"Peer IP address: {ip}")

    local_name = input("Enter peer name: ")

    m_sock.sendto(f"register {local_name} {ip} {m_port} {p_port}".encode(), (MANAGER_IP, MANAGER_PORT))

    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response != "SUCCESS"):
        print("Error: Failed to register with manager")
        sys.exit(1)

    threading.Thread(target=messages_thread, daemon=True).start()
    threading.Thread(target=commands_thread, daemon=True).start()

    threading.Event().wait()  # Keep main thread alive

    
def commands_thread():
    while True:
        command = input("> ")

        if not command.strip():
            continue

        match command.split()[0]:
            case "setup-dht":
                setup_dht(command)
            case "query-dht":
                query_dht(command)
            case "leave-dht":
                leave_dht(command)
            case "join-dht":
                join_dht(command)
            case "teardown-dht":
                teardown_dht(command)
            case "deregister":
                deregister(command)
            case _:
                print(f"Unknown command: {command}")


def messages_thread():
    while True:
        data, addr = p_sock.recvfrom(BUFFER_SIZE)
        args = data.decode().split()

        match args[0]:
            case "set-id":
                set_id(args)
            case "store-slice":
                store_slice(args)
            case "find-event":
                find_event(args)
            case "SUCCESS-query":
                print(f"id-seq: {args[2]}")
                fields = args[3].split(',')
                for field in fields:
                    key, value = field.split(':')
                    print(f"{key}: {value}")
            case "FAILURE-query":
                print(f"Storm event {args[1]} not found in the DHT.")
            case "reset-id":
                reset_id(args)
            case "rebuild-dht":
                rebuild_dht(args)
            case "teardown-dht":
                teardown_dht_slice(args)
            

# Helper functions
def set_port(sock_type):
    start = random.randint(33000, 33499)
    port = start
    while True:

        # Binds until it finds an open port
        try: 
            if(sock_type == "m"):
                m_sock.bind(("", port))
            elif(sock_type == "p"):
                p_sock.bind(("", port))
            else:
                print(f"Error: Invalid socket type {sock_type}")
                exit(1)
            return port
        except OSError:
            pass

        # Handle wrap-around
        port = 33000 if port == 33499 else port + 1  
        if port == start:
            print("Error: No available ports in range 33000-33499")
            sys.exit(1)

def find_next_prime(n):
    while True:
        n += 1
        if is_prime(n):
            return n

def is_prime(num):
    if num < 2:
        return False
    for i in range(2, int(num**0.5) + 1): #test divisibility up to sqrt(num)
        if num % i == 0:
            return False
    return True

def update_next_peer():
    global peers, id, ring_size, next_peer

    next_peer = next(p for p in peers if p["id"] == (id + 1) % ring_size) # Get next peer in ring

def clean(val):
    v = val.strip().replace(' ', '_')
    return v if v else 'n/a'

# Commands
def setup_dht(command):
    global id, ring_size, next_peer, s, year

    if(len(command.split()) != 4):
        print("Error: Invalid setup-dht command format. Usage: setup-dht <name> <ring_size> <year>")
        return

    year = int(command.split()[3])

    m_sock.sendto(command.encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    args = data.decode().split()

    if args[0] != "SUCCESS":
        print("Error: Failed to set up DHT")
        return
    
    # Leader is id 0
    id = 0

    # Add selected peers to dictionary
    ring_size = int(command.split()[2])
    for i in range(ring_size):
        offset = 1 + i*3
        peers.append({'name': args[offset], 'ip': args[offset + 1], 'p_port': args[offset + 2], 'id': i})
        print(f"Peer {args[offset]} selected for DHT")

    # Send set id to all selected peers, excluding self
    for peer in peers:
        if (peer['id'] != 0):
            p_sock.sendto(f"set-id {peer['id']} {ring_size} {' '.join(args[1:])}".encode(), (peer['ip'], int(peer['p_port'])))

    update_next_peer()

    # Read data
    filename = f"details-{year}.csv"

    with open(filename, 'r') as f:
        entries = sum(1 for _ in f) - 1

    s = find_next_prime(entries * 2)
    record_counts = {p['id']: 0 for p in peers}

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_id = int(row['EVENT_ID'])
            state = clean(row['STATE'])
            row_year = clean(row['YEAR'])
            month_name = clean(row['MONTH_NAME'])
            event_type = clean(row['EVENT_TYPE'])
            cz_type = clean(row['CZ_TYPE'])
            cz_name = clean(row['CZ_NAME'])
            injuries_direct = clean(row['INJURIES_DIRECT'])
            injuries_indirect = clean(row['INJURIES_INDIRECT'])
            deaths_direct = clean(row['DEATHS_DIRECT'])
            deaths_indirect = clean(row['DEATHS_INDIRECT'])
            damage_property = clean(row['DAMAGE_PROPERTY'])
            damage_crops = clean(row['DAMAGE_CROPS'])
            tor_f_scale = clean(row['TOR_F_SCALE'])

            pos = event_id % s
            peer_id = pos % ring_size

            time.sleep(0.001)
            p_sock.sendto(f"store-slice {peer_id} {event_id} {state} {row_year} {month_name} {event_type} {cz_type} {cz_name} {injuries_direct} {injuries_indirect} {deaths_direct} {deaths_indirect} {damage_property} {damage_crops} {tor_f_scale} {s} {year}".encode(), (next_peer['ip'], int(next_peer['p_port'])))
            record_counts[peer_id] += 1
    
    for p in peers:
        print(f"Peer {p['id']} ({p['name']}): {record_counts[p['id']]} records")
            
    m_sock.sendto(f"dht-complete {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))

def query_dht(command):
    m_sock.sendto(f"query-dht {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    args = data.decode().split()

    p_sock.sendto(f"find-event {command.split()[1]} {local_name} {ip} {p_port} none".encode(), (args[2], int(args[3])))

def leave_dht(command):
    m_sock.sendto(f"leave-dht {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response != "SUCCESS"):
        print("Error: Failed to leave DHT")
        return
    
    dht_slice.clear()
    print("Left DHT and cleared local slice")
    p_sock.sendto(f"reset-id 0".encode(), (next_peer['ip'], int(next_peer['p_port'])))

def join_dht(command):
    m_sock.sendto(f"join-dht {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response.split()[0] != "SUCCESS"):
        print("Error: Failed to join DHT")
        return

    p_sock.sendto(f"rebuild-dht {local_name} joining {ip} {p_port}".encode(), (response.split()[2], int(response.split()[3])))
    m_sock.sendto(f"dht-rebuilt {local_name} {response.split()[1]}".encode(), (MANAGER_IP, MANAGER_PORT))

    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response != "SUCCESS"):
        print("Error: Manager failed to acknowledge DHT rebuild")
        return

def teardown_dht(command):
    m_sock.sendto(f"teardown-dht {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response != "SUCCESS"):
        print("Error: Failed to tear down DHT")
        return
    
    p_sock.sendto(f"teardown-dht".encode(), (next_peer['ip'], int(next_peer['p_port'])))

def deregister(command):
    m_sock.sendto(f"deregister {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
    data, addr = m_sock.recvfrom(BUFFER_SIZE)
    response = data.decode()
    if(response != "SUCCESS"):
        print("Error: Failed to deregister with manager")
        os._exit(1)
    else:
        print("Deregistered with manager successfully")
        os._exit(0)

def send_dht_data():
    global s, year
    # Construct new DHT
    filename = f"details-{year}.csv"

    with open(filename, 'r') as f:
        entries = sum(1 for _ in f) - 1

    s = find_next_prime(entries * 2)
    record_counts = {p['id']: 0 for p in peers}


    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_id = int(row['EVENT_ID'])
            state = clean(row['STATE'])
            row_year = clean(row['YEAR'])
            month_name = clean(row['MONTH_NAME'])
            event_type = clean(row['EVENT_TYPE'])
            cz_type = clean(row['CZ_TYPE'])
            cz_name = clean(row['CZ_NAME'])
            injuries_direct = clean(row['INJURIES_DIRECT'])
            injuries_indirect = clean(row['INJURIES_INDIRECT'])
            deaths_direct = clean(row['DEATHS_DIRECT'])
            deaths_indirect = clean(row['DEATHS_INDIRECT'])
            damage_property = clean(row['DAMAGE_PROPERTY'])
            damage_crops = clean(row['DAMAGE_CROPS'])
            tor_f_scale = clean(row['TOR_F_SCALE'])

            pos = event_id % s
            peer_id = pos % ring_size

            time.sleep(0.001)
            p_sock.sendto(f"store-slice {peer_id} {event_id} {state} {row_year} {month_name} {event_type} {cz_type} {cz_name} {injuries_direct} {injuries_indirect} {deaths_direct} {deaths_indirect} {damage_property} {damage_crops} {tor_f_scale} {s} {year}".encode(), (next_peer['ip'], int(next_peer['p_port'])))
            record_counts[peer_id] += 1

    for p in peers:
        print(f"Peer {p['id']} ({p['name']}): {record_counts[p['id']]} records")

# Message handlers

def set_id(args):
    global id, ring_size

    peers.clear()

    id = int(args[1])
    print(f"Assigned ID {id}")

    ring_size = int(args[2])
    for i in range(ring_size):
        offset = 3 + i*3
        peers.append({'name': args[offset], 'ip': args[offset + 1], 'p_port': args[offset + 2], 'id': i})
        print(f"Peer {args[offset]} selected for DHT")
    
    update_next_peer()

def store_slice(args):
    global s, year

    if(int(args[1]) != id):
        print(f"Args length: {len(args)}")
        print(f"Received store-slice for id {args[1]}, but my id is {id}. Passing message to next peer.")
        p_sock.sendto(' '.join(args).encode(), (next_peer['ip'], int(next_peer['p_port'])))
    else:
        s = int(args[16])
        year = int(args[17])
        dht_slice[int(args[2]) % s] = {
                'state': args[3],
                'year': args[4],
                'month_name': args[5],
                'event_type': args[6],
                'cz_type': args[7],
                'cz_name': args[8],
                'injuries_direct': args[9],
                'injuries_indirect': args[10],
                'deaths_direct': args[11],
                'deaths_indirect': args[12],
                'damage_property': args[13],
                'damage_crops': args[14],
                'tor_f_scale': args[15]
            }
        print(f"Stored slice for event_id {args[2]}")
        
def find_event(args):
    pos = int(args[1]) % s
    peer_id = pos % ring_size

    if(peer_id == id):
        if(dht_slice.get(pos) is None):
            print(f"Event {args[1]} not found in DHT slice")
            p_sock.sendto(f"FAILURE-query {args[1]}".encode(), (args[3], int(args[4])))
        else:
            print(f"Found event {args[1]} in DHT slice")

            record = dht_slice[pos]
            record_str = ','.join(f"{k}:{v}" for k, v in record.items())

            if(args[5] == "none"):
                id_seq = f"{id}"
            else:
                id_seq = f"{args[5]}->{id}"
            
            args[5] = id_seq

            p_sock.sendto(f"SUCCESS-query {args[1]} {id_seq} {record_str}".encode(), (args[3], int(args[4])))
    else:
        print(f"Received find-event for event_id {args[1]}, but it belongs to peer {peer_id}. Passing message to next peer.")

        if(args[5] == "none"):
            id_seq = f"{id}"
        else:
            id_seq = f"{args[5]}->{id}"
        
        args[5] = id_seq
        p_sock.sendto(' '.join(args).encode(), (next_peer['ip'], int(next_peer['p_port'])))

def reset_id(args):
    global id, ring_size

    if(int(args[1]) == ring_size - 1):
        # Gone back to original propigation
        p_sock.sendto(f"rebuild-dht {local_name} leaving".encode(), (next_peer['ip'], int(next_peer['p_port'])))
        m_sock.sendto(f"dht-rebuilt {local_name} {next_peer['name']}".encode(), (MANAGER_IP, MANAGER_PORT))
        data, addr = m_sock.recvfrom(BUFFER_SIZE)
        response = data.decode()
        if(response != "SUCCESS"):
            print("Error: Manager failed to acknowledge DHT rebuild")
    else:

        p_sock.sendto(f"reset-id {(int(args[1]) + 1)}".encode(), (next_peer['ip'], int(next_peer['p_port'])))

        id = int(args[1])
        ring_size = ring_size - 1
        print(f"Reset ID to {id} and updated ring size to {ring_size}")

def rebuild_dht(args):
    global ring_size, peers, next_peer, s, year, id

    id = 0

    if(args[2] == "leaving"):
        remaining = [p for p in peers if p['name'] != args[1]]
        
        # find local peer index and assign ids from there
        local_idx = next(i for i, p in enumerate(remaining) if p['name'] == local_name)
        for i, p in enumerate(remaining):
            p['id'] = (i - local_idx) % len(remaining)
        
        # sort by new id
        peers = sorted(remaining, key=lambda p: p['id'])

    elif(args[2] == "joining"):
        peers.append({'name': args[1], 'ip': args[3], 'p_port': args[4], 'id': ring_size})
    else:
        print(f"Error: Invalid rebuild reason {args[2]}")
        exit(1)
    
    # Send new list of peers
    peer_str = ' '.join(f"{p['name']} {p['ip']} {p['p_port']}" for p in peers)
    for p in peers:
        if(p['name'] != local_name):
            p_sock.sendto(f"set-id {p['id']} {len(peers)} {peer_str}".encode(), (p['ip'], int(p['p_port'])))

    update_next_peer()

    ring_size = len(peers)

    threading.Thread(target=send_dht_data, daemon=True).start()
    
    

def teardown_dht_slice(args):
    if(id == 0): #Leader
        dht_slice.clear()
        print("Tore down DHT and cleared local slice")

        m_sock.sendto(f"teardown-complete {local_name}".encode(), (MANAGER_IP, MANAGER_PORT))
        data, addr = m_sock.recvfrom(BUFFER_SIZE)
        response = data.decode()

        if(response != "SUCCESS"):
            print("Error: Failed to receive teardown complete acknowledgement from manager")

    else:
        p_sock.sendto(f"teardown-dht".encode(), (next_peer['ip'], int(next_peer['p_port'])))
        dht_slice.clear()
        print("Tore down DHT and cleared local slice")


if __name__ == "__main__":
    main()

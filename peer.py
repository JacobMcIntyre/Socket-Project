import sys
import socket
 
MANAGER_IP = "null"  # Treating as constants, set by args
MANAGER_PORT = 0

def main():

    # Check args
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <manager_ip> <manager_port>")
        sys.exit(1)
 
    MANAGER_IP = sys.argv[1]
    MANAGER_PORT = int(sys.argv[2])

    if(MANAGER_PORT < 33000 or MANAGER_PORT > 33499):
        print("Error: Port number must be between 33000 and 33499")
        sys.exit(1)
 

    
 
if __name__ == "__main__":
    main()
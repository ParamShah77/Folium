import socket
import requests

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def probe_api():
    print(f"Checking port 8000: {'Open' if check_port(8000) else 'Closed'}")
    if check_port(8000):
        try:
            r = requests.get('http://localhost:8000/health', timeout=2)
            print(f"GET /health: {r.status_code} - {r.text}")
            r = requests.get('http://localhost:8000/docs', timeout=2)
            print(f"GET /docs: {r.status_code}")
        except Exception as e:
            print(f"Error probing API: {e}")

if __name__ == "__main__":
    probe_api()

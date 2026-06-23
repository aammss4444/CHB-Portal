import requests

try:
    response = requests.get('http://127.0.0.1:8080/api/requirements/dashboard/admin-stats', headers={'ngrok-skip-browser-warning': '69420'})
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

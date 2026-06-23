import urllib.request
import urllib.error

req = urllib.request.Request(
    'http://127.0.0.1:8080/api/auth/me?ngrok-skip-browser-warning=69420',
    method='GET',
    headers={'Origin': 'http://localhost:5173', 'Authorization': 'Bearer test'}
)

try:
    res = urllib.request.urlopen(req)
    print(res.headers)
    print(res.read())
except urllib.error.HTTPError as e:
    print(e.code)
    print(e.headers)
    print(e.read())

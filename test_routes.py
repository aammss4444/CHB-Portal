from app.main import app

for route in app.routes:
    methods = getattr(route, 'methods', None)
    print(f"{methods} {getattr(route, 'path', route.name)}")

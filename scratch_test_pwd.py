import time
from app.core.security import verify_password

start = time.time()
result = verify_password("password123", "$2b$12$bx5ScHPiSLEQFZTbaRxdjOcuXnYuK7r54ohnxVpper7wEr31H8zqm")
print(f"Result: {result}, Time taken: {time.time() - start:.2f}s")

import json

with open('CHB_Portal.postman_collection.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def find_auth_requests(items, prefix=''):
    for item in items:
        if 'item' in item:
            find_auth_requests(item['item'], prefix + item['name'] + ' > ')
        elif 'request' in item:
            url = item['request']['url']['raw'] if isinstance(item['request']['url'], dict) else item['request']['url']
            if '/api/auth' in url:
                print(f"{item['request']['method']} {url} - {item['name']}")

find_auth_requests(data['item'])

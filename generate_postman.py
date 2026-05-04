import json
import uuid
from app.main import app

def generate_postman_collection():
    openapi_schema = app.openapi()
    
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "CHB Portal - Complete API Collection",
            "description": "Complete API collection for the Clock Hour Basis (CHB) Portal Backend.\n\n**How to use:**\n1. Set the `baseUrl` variable to your server (default: http://localhost:8000)\n2. Call 'Login For Access Token' first - it auto-saves the token\n3. All other requests use the saved token automatically",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [],
        "variable": [
            {
                "key": "baseUrl",
                "value": "http://localhost:8000",
                "type": "string"
            },
            {
                "key": "accessToken",
                "value": "",
                "type": "string"
            }
        ]
    }

    # Grouping by tags
    folders = {}

    paths = openapi_schema.get("paths", {})
    components = openapi_schema.get("components", {}).get("schemas", {})

    def resolve_schema(schema, is_response=False):
        if not schema:
            return None
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            return resolve_schema(components.get(ref_name), is_response)
        
        if schema.get("type") == "object":
            example = {}
            for prop, details in schema.get("properties", {}).items():
                if "$ref" in details:
                    example[prop] = resolve_schema(details, is_response)
                elif "anyOf" in details:
                    valid_anyof = [d for d in details["anyOf"] if d.get("type") and d.get("type") != "null"]
                    if valid_anyof:
                        example[prop] = resolve_schema({"properties": {"tmp": valid_anyof[0]}, "type": "object"}, is_response)["tmp"]
                    else:
                        example[prop] = None
                elif details.get("type") == "array":
                    items = details.get("items", {})
                    example[prop] = [resolve_schema(items, is_response)]
                else:
                    # Default values for types
                    t = details.get("type")
                    fmt = details.get("format")
                    if t == "string":
                        # Better examples for frontend
                        if "email" in prop: example[prop] = "user@example.com"
                        elif "date" in prop or fmt == "date": example[prop] = "2026-05-01"
                        elif fmt == "date-time": example[prop] = "2026-05-01T10:00:00Z"
                        elif "token" in prop: example[prop] = "eyJhbGciOiJIUzI1Ni..."
                        elif "id" in prop and t == "string": example[prop] = str(uuid.uuid4())
                        else: example[prop] = details.get("example", "string")
                    elif t == "integer":
                        example[prop] = details.get("example", 1)
                    elif t == "number":
                        example[prop] = details.get("example", 10.5)
                    elif t == "boolean":
                        example[prop] = details.get("example", True)
                    else:
                        example[prop] = None
            return example
        return None

    for path, methods in paths.items():
        for method, details in methods.items():
            tag = details.get("tags", ["General"])[0]
            if tag not in folders:
                folders[tag] = {
                    "name": tag,
                    "item": []
                }
            
            # Request Body
            req_body = None
            if "requestBody" in details:
                content = details["requestBody"].get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    example = resolve_schema(schema)
                    req_body = {
                        "mode": "raw",
                        "raw": json.dumps(example, indent=2) if example else "{}",
                        "options": {
                            "raw": {
                                "language": "json"
                            }
                        }
                    }
                elif "application/x-www-form-urlencoded" in content:
                    if path == "/api/auth/login":
                        req_body = {
                            "mode": "urlencoded",
                            "urlencoded": [
                                {"key": "username", "value": "admin@chb.gov.in", "type": "text"},
                                {"key": "password", "value": "Admin@123", "type": "text"}
                            ]
                        }

            # Sample Response
            responses = []
            success_res = details.get("responses", {}).get("200") or details.get("responses", {}).get("201")
            if success_res:
                res_content = success_res.get("content", {}).get("application/json", {})
                res_schema = res_content.get("schema", {})
                res_data = resolve_schema(res_schema, is_response=True)
                
                # Wrap in standard envelope if not already
                if res_data and "status" not in res_data:
                    res_data = {
                        "status": "success",
                        "message": "Operation completed successfully",
                        "data": res_data
                    }
                elif not res_data:
                    res_data = {
                        "status": "success",
                        "message": "Operation completed successfully",
                        "data": {}
                    }

                responses.append({
                    "name": "Successful Response",
                    "originalRequest": {
                        "method": method.upper(),
                        "header": [],
                        "url": {
                            "raw": "{{baseUrl}}" + path,
                            "host": ["{{baseUrl}}"],
                            "path": path.strip("/").split("/")
                        }
                    },
                    "status": "OK" if "200" in details.get("responses", {}) else "Created",
                    "code": 200 if "200" in details.get("responses", {}) else 201,
                    "_postman_previewlanguage": "json",
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "cookie": [],
                    "body": json.dumps(res_data, indent=2)
                })

            # URL and Path Variables
            url_path = path.replace("{", ":").replace("}", "")
            
            request_item = {
                "name": details.get("summary") or details.get("operationId") or path,
                "request": {
                    "method": method.upper(),
                    "header": [
                        {"key": "Content-Type", "value": "application/json"}
                    ],
                    "url": {
                        "raw": "{{baseUrl}}" + url_path,
                        "host": ["{{baseUrl}}"],
                        "path": url_path.strip("/").split("/")
                    },
                    "description": details.get("description", "")
                },
                "response": responses
            }

            if req_body:
                request_item["request"]["body"] = req_body

            # Auth
            if path != "/api/auth/login" and path != "/api/auth/candidate/register":
                request_item["request"]["auth"] = {
                    "type": "bearer",
                    "bearer": [
                        {"key": "token", "value": "{{accessToken}}", "type": "string"}
                    ]
                }

            # Special case for Login to save token
            if path == "/api/auth/login":
                request_item["event"] = [
                    {
                        "listen": "test",
                        "script": {
                            "exec": [
                                "var jsonData = pm.response.json();",
                                "if (jsonData && jsonData.access_token) {",
                                "    pm.collectionVariables.set('accessToken', jsonData.access_token);",
                                "    console.log('Access token saved!');",
                                "}"
                            ],
                            "type": "text/javascript"
                        }
                    }
                ]

            folders[tag]["item"].append(request_item)

    # Sort folders by tag name
    sorted_tags = sorted(folders.keys())
    for tag in sorted_tags:
        collection["item"].append(folders[tag])

    with open("CHB_Portal.postman_collection.json", "w") as f:
        json.dump(collection, f, indent=2)
    
    print(f"Successfully generated collection with {len(paths)} paths.")

if __name__ == "__main__":
    generate_postman_collection()

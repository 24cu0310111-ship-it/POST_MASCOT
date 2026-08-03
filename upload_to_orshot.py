import base64
import json
import urllib.request

image_path = "/Users/aryan/Desktop/Post-mascot/india_post_mascot_v8_final.png"
with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

data_uri = f"data:image/png;base64,{encoded_string}"

url = "https://mcp.orshot.com/mcp"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer os-uex53i0zc50adp6u5oxd60segu34v0"
}

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "orshot_upload_brand_image",
        "arguments": {
            "file": data_uri,
            "name": "India Post Mascot v8",
            "tags": ["mascot", "india post"]
        }
    }
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
try:
    response = urllib.request.urlopen(req)
    result = response.read().decode('utf-8')
    print(result)
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))

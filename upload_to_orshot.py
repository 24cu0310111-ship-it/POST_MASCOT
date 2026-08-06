import base64
import json
import os
import sys
import urllib.request

API_KEY = os.getenv("ORSHOT_API_KEY")
if not API_KEY:
    print("Error: ORSHOT_API_KEY environment variable not set.")
    print("Add it to your .env file or export it before running this script.")
    sys.exit(1)

if len(sys.argv) < 2:
    print(f"Usage: python {sys.argv[0]} <image_path>")
    print("Example: python upload_to_orshot.py ./mascot.png")
    sys.exit(1)

image_path = sys.argv[1]
if not os.path.exists(image_path):
    print(f"Error: File not found: {image_path}")
    sys.exit(1)

with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

data_uri = f"data:image/png;base64,{encoded_string}"

url = "https://mcp.orshot.com/mcp"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

basename = os.path.basename(image_path)
name = os.path.splitext(basename)[0].replace("_", " ").title()

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "orshot_upload_brand_image",
        "arguments": {
            "file": data_uri,
            "name": name,
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

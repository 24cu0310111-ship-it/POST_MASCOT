import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.sse import sse_client

API_KEY = os.getenv("ORSHOT_API_KEY")
if not API_KEY:
    print("Error: ORSHOT_API_KEY environment variable not set.")
    print("Add it to your .env file or export it before running this script.")
    exit(1)
MCP_URL = "https://mcp.orshot.com/mcp"
OUTPUT_DIR = os.path.expanduser("~/Desktop/Post-mascot")

PROMPT = """
Design a brand character and mascot for India Post. 
The character must communicate: Trust & Reliability, Public Service, Inclusivity, Indian Culture & Heritage, Digital Innovation, Friendly Personality, Nationwide Connectivity.
The mascot should represent the "Modern Ambassador": A familiar face introducing a modern service, blending tradition with digital transformation (e.g. holding a letter alongside a QR code). 
The aesthetic should be welcoming, utilizing rounded shapes (baby schema), large eyes for friendliness, and wearing a recognizable postal uniform (Khaki, Red, Cream). The expression should invite connection without being overly dramatic. 
The mascot bridges the gap between the operational trust (like biometric verification) and emotional care (like a neighborhood guardian), becoming the visual identity of India Post's digital era.
"""

async def main():
    print(f"Connecting to {MCP_URL}...")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json, text/event-stream"
    }
    
    # Establish SSE connection to Orshot MCP
    async with sse_client(url=MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to Orshot MCP server.")
            
            print("Requesting mascot design template creation...")
            try:
                # We will call the create_template_design tool with the synthesized prompt elements.
                # Since Orshot is a layout-based engine, we construct a descriptive text element for the AI or designer prompt representation.
                result = await session.call_tool(
                    "orshot_create_template_design",
                    arguments={
                        "name": "India Post Mascot Concept",
                        "size": "1080x1080",
                        "pages_data": [
                            {
                                "elements": [
                                    {
                                        "id": "concept_text",
                                        "type": "text",
                                        "text": PROMPT,
                                        "position": {"x": 50, "y": 50},
                                        "size": {"width": 980, "height": 980},
                                        "style": {
                                            "fontSize": "30px",
                                            "color": "#000000"
                                        }
                                    }
                                ],
                                "backgroundColor": "#ffffff"
                            }
                        ],
                        "includeThumbnails": True
                    }
                )
                print("Mascot template design created successfully!")
                
                # Write the response and prompt to output files
                with open(os.path.join(OUTPUT_DIR, "concept_prompt.txt"), "w") as f:
                    f.write(PROMPT)
                
                with open(os.path.join(OUTPUT_DIR, "orshot_response.json"), "w") as f:
                    # Convert response to dict for serialization if it's a Pydantic model
                    json.dump(result.model_dump() if hasattr(result, "model_dump") else str(result), f, indent=2)
                    
                print(f"Outputs saved to {OUTPUT_DIR}")
                
            except Exception as e:
                print(f"Error calling Orshot tool: {e}")

if __name__ == "__main__":
    asyncio.run(main())

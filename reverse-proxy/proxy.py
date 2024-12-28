from fastapi import FastAPI, Request,Response
import httpx
import uvicorn
from urllib.parse import urljoin

app = FastAPI()
client = httpx.AsyncClient(follow_redirects=True)

# Constants
PORT = 8000

BASE_PATH = "https://vercel-output-s3.s3.ap-south-1.amazonaws.com/__output"

@app.get("/{full_path:path}")
async def proxy_handler(request: Request, full_path: str = ""):
    try:
        # Extract subdomain from hostname
        print("path",full_path)
        hostname = request.headers.get("host", "")
        subdomain = hostname.split(".")[0]
        print(subdomain)
        
        # Construct target URL
        path = full_path if full_path else "index.html"

        target_url = f"{BASE_PATH}/{subdomain}/{path}"
        print(target_url)
        
        # Forward the request
        response = await client.get(target_url)
        
        # Get content type from response or set default
        content_type = response.headers.get("content-type", "text/html")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={"content-type": content_type}
        )

        
    except Exception as e:
        raise(e)
        return {"error": f"Proxy error: {str(e)}"}

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

if __name__ == "__main__":
    print(f"Reverse Proxy Running on port {PORT}")
    uvicorn.run(app, host="localhost", port=PORT)




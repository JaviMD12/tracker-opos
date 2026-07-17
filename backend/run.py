import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # proxy_headers=True: confia en X-Forwarded-Proto/X-Forwarded-For del
    # proxy inverso (nginx/Caddy delante en produccion), para que
    # request.url_for() calcule "https://" en vez de "http://" al construir
    # el redirect_uri del login con Google. forwarded_allow_ips por defecto
    # solo confia en 127.0.0.1 (el proxy en la misma maquina); si el proxy
    # esta en otra IP, hay que pasarla explicitamente.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )

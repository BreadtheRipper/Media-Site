from waitress import serve
from app import create_app  # Replace with your actual app import

app = create_app()

# Configure waitress with custom settings
serve(
    app,
    host='192.168.0.254',
    port=5000,
    threads=16,               # Adjusted for 4 cores, 8 threads
    connection_limit=5000,    # Increased to handle many simultaneous connections
    max_request_body_size=1073741824,  # Allow up to 1GB uploads if needed
    channel_timeout=3600,      # Set a long timeout (1 hour)
    expose_tracebacks=True
)

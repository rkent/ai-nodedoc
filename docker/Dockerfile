FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3 and essential tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment so pip works without --break-system-packages
ENV VENV=/opt/venv
RUN python3 -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy repository contents
WORKDIR /app
COPY . .

# Make the main script executable
RUN chmod +x node_docs.py

# Default: show help.
# To generate docs, override with:
#   docker run --rm \
#     -e ANTHROPIC_API_KEY=<key> \
#     -v /path/to/ros_ws:/ros_ws:ro \
#     -v /path/to/output:/output \
#     <image> /ros_ws --output-dir /output
ENTRYPOINT ["python3", "node_docs.py"]
CMD ["--help"]

FROM python:3.12-slim-bookworm

LABEL maintainer="mcp-dosre"
LABEL description="DOS-era binary reverse-engineering tools MCP server"

# Binary-analysis tool chest. strings + od come from coreutils/binutils in the
# base image; the rest we install explicitly.
#   vim-common     -> xxd
#   bsdmainutils   -> hexdump
#   file           -> magic-byte sniffer
#   hexyl          -> colorised hex viewer
#   nasm           -> ndisasm (x86 disassembler, 16/32/64-bit)
#   binutils       -> strings (in case base image lacks it)
#   coreutils      -> md5sum, dd, stat
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim-common \
    bsdmainutils \
    file \
    hexyl \
    nasm \
    binutils \
    coreutils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastmcp \
    "mcp-knowledge-base @ https://github.com/jasonuithol/mcp-knowledge-base/archive/refs/tags/v0.2.1.tar.gz"

WORKDIR /app
COPY mcp-service.py .

EXPOSE 5175

CMD ["python", "mcp-service.py"]

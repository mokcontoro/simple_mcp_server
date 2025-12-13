"""CLI entry point for simple-mcp-server."""
import uvicorn


def main():
    """Start the MCP server."""
    uvicorn.run("main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

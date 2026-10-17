"""Native MCP stdio transport using the official optional Python MCP SDK."""
import asyncio
import json
from .agent_tools import AgentTools, tool_schemas


def create_server(*, permissions=None):
    try:
        from mcp.server.lowlevel import Server
        from mcp.types import Tool, TextContent
    except ImportError as exc:
        raise ImportError('Install nablamath[mcp] to run the MCP server') from exc
    server = Server('nabla-scientific-laboratory')
    tools = AgentTools(permissions)

    @server.list_tools()
    async def list_tools():
        return [Tool(**row) for row in tool_schemas() if row['name'] in tools.permissions.allowed_tools]

    @server.call_tool()
    async def call_tool(name, arguments):
        # Blocking numerical work and process supervision must not block the event loop.
        result = await asyncio.to_thread(tools.call,name,arguments)
        return [TextContent(type='text',text=json.dumps(result,sort_keys=True,allow_nan=False))]
    return server


async def serve():
    try:
        from mcp.server.stdio import stdio_server
    except ImportError as exc:
        raise ImportError('Install nablamath[mcp] to run the MCP server') from exc
    server = create_server()
    async with stdio_server() as (read_stream,write_stream):
        await server.run(read_stream,write_stream,server.create_initialization_options())


def main():
    asyncio.run(serve())


if __name__ == '__main__':
    main()

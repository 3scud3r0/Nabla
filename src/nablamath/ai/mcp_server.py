"""Native MCP stdio transport using the official optional Python MCP SDK."""
import asyncio
import json
from .agent_tools import AgentTools, tool_schemas


def create_server(*, permissions=None, include_verifier=False, max_concurrent=4):
    try:
        from mcp.server.lowlevel import Server
        from mcp.types import Tool, TextContent, CallToolResult
    except ImportError as exc:
        raise ImportError('Install nablamath[mcp] to run the MCP server') from exc
    server = Server('nabla-scientific-laboratory')
    if include_verifier and permissions is None:
        from ..agents.permissions import Permissions
        permissions = Permissions(frozenset(t['name'] for t in tool_schemas())|{'verify_conjecture'},max_calls=100)
    tools = AgentTools(permissions,max_concurrent=max_concurrent)
    verifier_schema = {'type':'object','properties':{
        'goal':{'type':'string','minLength':1,'maxLength':4096},
        'assumptions':{'type':'array','items':{'type':'string','maxLength':4096},'maxItems':32}},
        'required':['goal'],'additionalProperties':False}

    @server.list_tools()
    async def list_tools():
        listed = [Tool(**row) for row in tool_schemas() if row['name'] in tools.permissions.allowed_tools]
        if include_verifier and 'verify_conjecture' in tools.permissions.allowed_tools:
            listed.append(Tool(name='verify_conjecture',description='Controlled rational/polynomial conjecture with a five-second hard wall-clock limit; not a Lean proof',inputSchema=verifier_schema))
        return listed

    @server.call_tool()
    async def call_tool(name, arguments):
        # Blocking numerical work and process supervision must not block the event loop.
        if name == 'verify_conjecture' and include_verifier:
            from jsonschema import Draft202012Validator
            Draft202012Validator(verifier_schema).validate(arguments)
            verification = await asyncio.to_thread(tools.verify_conjecture,arguments)
            data = verification.to_data()
            from ..calc.receipt import receipt
            result = receipt('ai.verify_conjecture',arguments,data,backend='z3')
        else:
            result = await asyncio.to_thread(tools.call,name,arguments)
        raw = json.dumps(result,sort_keys=True,allow_nan=False)
        return CallToolResult(content=[TextContent(type='text',text=raw)],structuredContent={
            'data':result['result'],'audit_receipt':raw,'content_id':result['content_id']})
    return server


async def serve(*, include_verifier=False):
    try:
        from mcp.server.stdio import stdio_server
    except ImportError as exc:
        raise ImportError('Install nablamath[mcp] to run the MCP server') from exc
    server = create_server(include_verifier=include_verifier)
    async with stdio_server() as (read_stream,write_stream):
        await server.run(read_stream,write_stream,server.create_initialization_options())


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-claims',action='store_true',help='Expose the bounded SMT conjecture verifier')
    args = parser.parse_args()
    asyncio.run(serve(include_verifier=args.verify_claims))


if __name__ == '__main__':
    main()

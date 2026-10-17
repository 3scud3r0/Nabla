"""Schema coverage, actual tool processes, SMT verdicts and MCP client transport."""
import asyncio
import json
from pathlib import Path
import sys
import pytest
from nablamath.ai.agent_tools import tool_schemas,openai_tools,AgentTools
from nablamath.ai.sandbox_verifier import verify_claim,SandboxVerifier
from nablamath.calc.catalog import catalog
from nablamath.calc.receipt import verify_receipt
from nablamath.agents.permissions import Permissions
from nablamath.formal.statement import FormalStatement


def test_all_catalog_schemas_valid_and_cover_real_examples():
    jsonschema = pytest.importorskip('jsonschema')
    schemas = tool_schemas()
    assert {t['name'] for t in schemas} == {o['name'] for o in catalog()['operations']}
    assert len(openai_tools()) == len(schemas)
    cases = json.loads((Path(__file__).resolve().parents[1]/'examples/science/catalog_cases.json').read_text())
    for tool in schemas:
        jsonschema.Draft202012Validator.check_schema(tool['inputSchema'])
        if tool['name'] in cases:
            jsonschema.Draft202012Validator(tool['inputSchema']).validate(cases[tool['name']])


def test_agent_tool_subprocess_contracts_permissions_and_call_budget():
    pytest.importorskip('jsonschema')
    tools = AgentTools(Permissions(frozenset({'beta_binomial'}),max_calls=1))
    result = tools.call('beta_binomial',{'successes':2,'trials':3})
    assert result['result']['mean'] == '3/5' and verify_receipt(result)
    with pytest.raises(PermissionError,match='budget'):
        tools.call('beta_binomial',{'successes':0,'trials':1})
    with pytest.raises(PermissionError):
        tools.call('evaluate',{'source':'2'})
    with pytest.raises(ValueError):
        tools.call('beta_binomial',{'successes':2,'trials':3,'code':'print(1)'})


def test_smt_claim_verdicts_are_not_promoted_to_formal_proofs():
    pytest.importorskip('z3')
    supported = verify_claim(FormalStatement.equality('x+1','1+x'))
    assert supported['result']['verdict'] == 'supported_in_fragment'
    refuted = verify_claim(FormalStatement.equality('x+1','x'))
    assert refuted['result']['verdict'] == 'refuted'
    assert refuted['result']['verification']['exact_replay']
    unsupported = verify_claim(FormalStatement.equality('x*x','x'))
    assert unsupported['result']['verdict'] == 'unverified'
    assert verify_receipt(supported) and supported['formal_proof'] is False
    with pytest.raises(ValueError,match='rejected'):
        SandboxVerifier().require_supported(FormalStatement.equality('x+1','x'))


def test_actual_mcp_stdio_initialization_tools_and_calculation():
    pytest.importorskip('mcp'); pytest.importorskip('jsonschema')
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def exercise():
        parameters = StdioServerParameters(command=sys.executable,args=['-m','nablamath.ai.mcp_server'])
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as client:
                initialized = await client.initialize()
                assert initialized.serverInfo.name == 'nabla-scientific-laboratory'
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == {tool['name'] for tool in tool_schemas()}
                result = await client.call_tool('beta_binomial',{'successes':2,'trials':3})
                assert not result.isError
                assert json.loads(result.content[0].text)['result']['mean'] == '3/5'
                invalid = await client.call_tool('unknown',{})
                assert invalid.isError
    asyncio.run(exercise())

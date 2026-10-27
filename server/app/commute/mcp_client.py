"""Small, bounded Streamable HTTP client for the pinned local read-only MCP.

The MCP SDK stays in the sidecar environment. Credentials exist only in headers;
provider response/error bodies are never echoed into application errors or logs.
"""
import asyncio,json,re,uuid
from urllib.parse import urlsplit
import httpx
from ..ai.provider import run_transport,strict_json
from ..common import ApiError

TOOLS=frozenset({'plan_trip','find_nearby','get_alerts'})
LIMIT=1_000_000

class McpClient:
    def __init__(self,url,api_key,transport=None,timeout=8):
        parsed=urlsplit(url)
        if (parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.username or parsed.password
                or parsed.path!='/mcp' or parsed.query or parsed.fragment):
            raise ValueError('Transit MCP must use an HTTP loopback /mcp endpoint')
        if not isinstance(api_key,str) or not api_key or len(api_key)>4096 or any(ord(c)<32 for c in api_key):
            raise ValueError('Transit MCP credential is missing or invalid')
        self.url=url;self._key=api_key;self.transport=transport;self.timeout=min(max(float(timeout),1),12)

    def call_tool(self,name,arguments):
        if name not in TOOLS or not isinstance(arguments,dict):
            raise ApiError(422,'mcp_tool_not_allowed','不支持这项交通查询。')
        async def work():
            async with asyncio.timeout(self.timeout):
                headers={'X-API-Key':self._key,'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
                async with httpx.AsyncClient(transport=self.transport,timeout=self.timeout,trust_env=False,follow_redirects=False,headers=headers) as http:
                    initialize=await self._rpc(http,'initialize',{'protocolVersion':'2025-11-25',
                        'capabilities':{},'clientInfo':{'name':'usyd-rental-agent2','version':'1.0'}})
                    version=initialize.get('protocolVersion')
                    if not isinstance(version,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',version):raise ValueError()
                    http.headers['MCP-Protocol-Version']=version
                    await self._rpc(http,'notifications/initialized',None,notification=True)
                    result=await self._rpc(http,'tools/call',{'name':name,'arguments':arguments})
                    if result.get('isError') is not False and result.get('isError') is not None:raise ValueError()
                    payload=result.get('structuredContent')
                    if not isinstance(payload,dict):raise ValueError()
                    return payload
        try:return run_transport(work(),self.timeout+.5)
        except (TimeoutError,httpx.TimeoutException):
            raise ApiError(504,'mcp_timeout','交通工具暂时响应较慢。') from None
        except (httpx.HTTPError,ValueError,KeyError,TypeError,UnicodeError):
            raise ApiError(502,'mcp_unavailable','交通工具暂时无法完成查询。') from None

    async def _rpc(self,http,method,params,notification=False):
        identifier=uuid.uuid4().hex
        request={'jsonrpc':'2.0','method':method}
        if params is not None:request['params']=params
        if not notification:request['id']=identifier
        raw=json.dumps(request,ensure_ascii=False,allow_nan=False).encode()
        if len(raw)>16000:raise ValueError()
        async with http.stream('POST',self.url,content=raw) as response:
            if response.status_code not in ((200,202,204) if notification else (200,)):raise ValueError()
            body=bytearray()
            async for chunk in response.aiter_bytes():
                if len(body)+len(chunk)>LIMIT:raise ValueError()
                body.extend(chunk)
            if notification:return None
            session=response.headers.get('mcp-session-id')
            if session:
                if not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}',session):raise ValueError()
                http.headers['Mcp-Session-Id']=session
            text=bytes(body).decode('utf-8')
            content_type=response.headers.get('content-type','').split(';')[0]
            if content_type=='application/json':envelopes=[strict_json(text)]
            elif content_type=='text/event-stream':
                envelopes=[];data=[]
                for line in (text+'\n\n').splitlines():
                    if line.startswith('data:'):data.append(line[5:].lstrip(' '))
                    elif not line and data:
                        envelopes.append(strict_json('\n'.join(data)));data=[]
                        if len(envelopes)>20:raise ValueError()
            else:raise ValueError()
            replies=[e for e in envelopes if isinstance(e,dict) and e.get('id')==identifier]
            if len(replies)!=1:raise ValueError()
            reply=replies[0]
            if reply.get('jsonrpc')!='2.0' or 'error' in reply or not isinstance(reply.get('result'),dict):raise ValueError()
            return reply['result']

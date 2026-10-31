import json,unittest
import httpx
from server.app.common import ApiError

def journey(depart='2026-10-28T08:30:00+11:00',arrive='2026-10-28T09:00:00+11:00'):
    return {'departure':depart,'arrival':arrive,'duration_min':20,'changes':1,'legs':[
        {'mode':'BUS','duration_min':10,'from':{'name':'A','departure':depart},'to':{'name':'B','arrival':'2026-10-28T08:40:00+11:00'},'route':'412'},
        {'mode':'BUS','duration_min':10,'from':{'name':'B','departure':'2026-10-28T08:50:00+11:00'},'to':{'name':'Fisher','arrival':arrive},'route':'413'}]}

class McpProtocolTests(unittest.TestCase):
    def test_oversized_valid_rpc_is_rejected_before_any_tool_call(self):
        from server.app.commute.mcp_client import McpClient
        sent=[]
        def respond(request):
            value=json.loads(request.content);sent.append(value['method'])
            return httpx.Response(200,json={'jsonrpc':'2.0','id':value['id'],'result':{
                'protocolVersion':'2025-11-25','padding':'x'*1_000_000}})
        client=McpClient('http://127.0.0.1:6401/mcp','test-key',transport=httpx.MockTransport(respond))
        with self.assertRaises(ApiError):client.call_tool('plan_trip',{})
        self.assertEqual(sent,['initialize'])

    def test_streamable_http_sequence_key_headers_and_structured_payload(self):
        from server.app.commute.mcp_client import McpClient
        sent=[]
        def respond(request):
            payload=json.loads(request.content);sent.append(payload)
            self.assertEqual(request.headers['X-API-Key'],'private-test-key')
            if payload['method']=='initialize':
                return httpx.Response(200,json={'jsonrpc':'2.0','id':payload['id'],'result':{'protocolVersion':'2025-11-25','capabilities':{},'serverInfo':{'name':'test','version':'1'}}})
            if payload['method']=='notifications/initialized':return httpx.Response(202)
            self.assertEqual(payload['params']['name'],'plan_trip')
            envelope={'jsonrpc':'2.0','id':payload['id'],'result':{'isError':False,'structuredContent':{'journeys':[journey()]}}}
            return httpx.Response(200,headers={'Content-Type':'text/event-stream'},text='event: message\ndata: '+json.dumps(envelope)+'\n\n')
        client=McpClient('http://127.0.0.1:6401/mcp','private-test-key',transport=httpx.MockTransport(respond))
        data=client.call_tool('plan_trip',{'detail':'summary'})
        self.assertEqual(len(data['journeys']),1)
        self.assertEqual([p['method'] for p in sent],['initialize','notifications/initialized','tools/call'])
        self.assertNotIn('private-test-key',json.dumps(sent))

    def test_only_loopback_no_redirects_no_arbitrary_tools_and_no_key_errors(self):
        from server.app.commute.mcp_client import McpClient
        for url in ('https://example.com/mcp','http://localhost.evil/mcp','http://user:secret@127.0.0.1/mcp','http://127.0.0.1/mcp?key=abc','http://127.0.0.1:6401/not-mcp'):
            with self.assertRaises(ValueError):McpClient(url,'secret-key')
        client=McpClient('http://127.0.0.1:6401/mcp','secret-key',transport=httpx.MockTransport(lambda _:httpx.Response(307,headers={'Location':'https://example.com/'})))
        with self.assertRaises(ApiError) as error:client.call_tool('plan_trip',{})
        self.assertNotIn('secret-key',str(error.exception))
        with self.assertRaises(ApiError):client.call_tool('execute_shell',{})

    def test_wrong_reply_id_and_error_payload_are_rejected_without_exposing_key(self):
        from server.app.commute.mcp_client import McpClient
        for envelope in ({'jsonrpc':'2.0','id':'wrong','result':{}},{'jsonrpc':'2.0','id':'wrong','error':{'message':'secret-key'}}):
            client=McpClient('http://127.0.0.1:6401/mcp','secret-key',transport=httpx.MockTransport(lambda _:httpx.Response(200,json=envelope)))
            with self.assertRaises(ApiError) as error:client.call_tool('plan_trip',{})
            self.assertNotIn('secret-key',str(error.exception))

class McpJourneyTests(unittest.TestCase):
    def test_elapsed_includes_waiting_and_never_uses_rounded_duration(self):
        from server.app.commute.mcp_journeys import normalize_journeys
        result=normalize_journeys({'journeys':[journey()]})[0]
        self.assertEqual(result['duration_minutes'],30)
        self.assertEqual(result['transfers'],1)
        self.assertEqual(result['transit_modes'],['bus'])
        self.assertEqual(result['legs'][0]['from'],'A')

    def test_bad_timestamps_and_unknown_modes_are_rejected_for_direct_fallback(self):
        from server.app.commute.mcp_journeys import normalize_journeys
        for changes in ({'arrival':'not a timestamp'},{'arrival':'2026-10-28T08:00:00+11:00'},{'changes':False}):
            with self.assertRaises(ApiError):normalize_journeys({'journeys':[{**journey(),**changes}]})
        item=journey();item['legs'][0]['mode']='UNKNOWN'
        with self.assertRaises(ApiError):normalize_journeys({'journeys':[item]})

    def test_early_and_late_are_checked_against_requested_arrival(self):
        from server.app.commute.mcp_journeys import normalize_journeys
        from server.app.commute.planner import timing_matches
        from datetime import datetime
        item=journey(arrive='2026-10-28T09:01:00+11:00');item['legs'][-1]['to']['arrival']=item['arrival']
        parsed=normalize_journeys({'journeys':[item]})[0]
        self.assertFalse(timing_matches(parsed,datetime.fromisoformat('2026-10-28T09:00:00+11:00')))

    def test_malformed_or_overlarge_leg_arrays_do_not_become_route_facts(self):
        from server.app.commute.mcp_journeys import normalize_journeys
        for legs in ([],[{}]*101,'bad'):
            with self.assertRaises(ApiError):normalize_journeys({'journeys':[{**journey(),'legs':legs}]})

class RouteProviderTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        self.direct_calls=[];self.tool_calls=[]
        self.direct=SimpleNamespace(tfnsw_key='server-secret',trips=lambda body:self.direct_calls.append(body) or {'journeys':[]})
        self.client=SimpleNamespace(call_tool=lambda name,args:self.tool_calls.append((name,args)) or {'journeys':[journey()]})
        self.body={'origin':{'latitude':-33.886384,'longitude':151.17822},
            'destination':{'latitude':-33.88630396441765,'longitude':151.190498785334},
            'arrival_at':'2026-10-28T09:00:00+11:00','allow_external':True}

    def test_routes_use_server_coordinates_and_mcp_with_elapsed_calculation(self):
        from server.app.commute.mcp_transit import TransitProvider
        response=TransitProvider(self.direct,client=self.client).trips(self.body)
        self.assertEqual(response['transport_backend'],'tfnsw_mcp')
        self.assertEqual(response['journeys'][0]['duration_minutes'],30)
        name,args=self.tool_calls[0];self.assertEqual(name,'plan_trip');self.assertTrue(args['arrive_by'])
        self.assertEqual(args['origin_type'],'coord');self.assertEqual(args['destination_type'],'coord')
        self.assertNotIn('server-secret',str(args));self.assertEqual(self.direct_calls,[])

    def test_unavailable_or_unknown_mode_mcp_uses_real_direct_fallback(self):
        from server.app.commute.mcp_transit import TransitProvider
        def failed(*_):raise ApiError(504,'mcp_timeout','provider timeout')
        self.client.call_tool=failed
        response=TransitProvider(self.direct,client=self.client).trips(self.body)
        self.assertTrue(response['fallback_used']);self.assertEqual(response['transport_backend'],'tfnsw_direct')
        self.assertEqual(self.direct_calls,[self.body])

    def test_fallback_shares_original_time_budget_without_mutating_direct_provider(self):
        from unittest.mock import patch
        from server.app.real_data.providers import DataProviders
        from server.app.commute.mcp_transit import TransitProvider
        original=DataProviders(env={'TFNSW_API_KEY':'test-key'});timeouts=[]
        def failed(*_):raise ApiError(504,'mcp_timeout','timeout')
        self.client.call_tool=failed
        def fallback(direct,body):timeouts.append(direct.timeout);return {'journeys':[]}
        with patch('server.app.commute.mcp_transit.monotonic',side_effect=[10,18]),patch.object(DataProviders,'trips',fallback):
            TransitProvider(original,client=self.client).trips(self.body)
        self.assertEqual(timeouts,[4]);self.assertEqual(original.timeout,12)

    def test_no_consent_or_other_destination_never_calls_either_service(self):
        from server.app.commute.mcp_transit import TransitProvider
        provider=TransitProvider(self.direct,client=self.client)
        for change in ({'allow_external':False},{'destination':{'latitude':-34.03,'longitude':150.66}}):
            with self.assertRaises(ApiError):provider.trips({**self.body,**change})
        self.assertEqual(self.direct_calls,[]);self.assertEqual(self.tool_calls,[])

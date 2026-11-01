"""Agent2's read-only MCP boundary and genuine direct-provider fallback."""
import os
from time import monotonic
from ..common import ApiError,now,require,shape
from ..real_data.providers import DataProviders,TFNSW_DOC
from ..real_data.intake import instant,coordinates
from .locations import valid_point
from .usyd import DESTINATION
from .mcp_client import McpClient
from .mcp_journeys import normalize_journeys

class TransitProvider:
    def __init__(self,direct,client=None,env=None):
        self.direct=direct;self.client=client
        env=os.environ if env is None else env
        self.last_status='not_queried'
        if client is None and env.get('RENTAL_TFNSW_MCP_URL') and env.get('RENTAL_TFNSW_MCP_ENABLED','1').lower() in ('1','true'):
            try:self.client=McpClient(env['RENTAL_TFNSW_MCP_URL'],getattr(direct,'tfnsw_key',''))
            except ValueError:self.last_status='invalid_configuration'

    def public_config(self):
        return {'enabled':self.client is not None,'backend':'tfnsw_mcp' if self.client else 'tfnsw_direct',
            'last_status':self.last_status,'fallback':'tfnsw_direct','tools':['plan_trip','find_nearby','get_alerts'] if self.client else []}

    def trips(self,body):
        shape(body,('origin','destination','arrival_at','allow_external'))
        require(body['allow_external'] is True,422,'external_query_required','Consent is required for this transit query.')
        origin,destination=coordinates(body['origin']),coordinates(body['destination'])
        require(valid_point(origin) and all(abs(destination[k]-DESTINATION[k])<.000001 for k in ('latitude','longitude')),
                422,'outside_commute_scope','The commute destination must be the USYD main campus.')
        arrival=instant(body['arrival_at']);started=monotonic();fallback_code=None
        if self.client:
            coord=lambda p:f"{p['longitude']:.7f}:{p['latitude']:.7f}:EPSG:4326"
            try:
                payload=self.client.call_tool('plan_trip',{'origin_id':coord(origin),'destination_id':coord(destination),
                    'origin_type':'coord','destination_type':'coord','when':arrival.isoformat(),'arrive_by':True,
                    'realtime':False,'detail':'summary','max_results':3})
                journeys=normalize_journeys(payload);self.last_status='ready'
                return {'provider':'tfnsw','transport_backend':'tfnsw_mcp','fallback_used':False,
                        'queried_at':now(),'query':body,'journeys':journeys,'source_url':TFNSW_DOC}
            except ApiError as error:fallback_code=error.code;self.last_status='fallback'
        direct=self.direct
        if isinstance(direct,DataProviders):
            # Each concurrent query gets its own bounded remaining timeout.
            direct=DataProviders(env={'TFNSW_API_KEY':self.direct.tfnsw_key},transport=self.direct.transport)
            direct.timeout=max(.25,min(self.direct.timeout,12-(monotonic()-started)))
        result=direct.trips(body)
        return {**result,'transport_backend':'tfnsw_direct','fallback_used':bool(fallback_code),
                **({'fallback_code':fallback_code} if fallback_code else {})}

    def tool(self,name,arguments):
        require(self.client is not None,503,'mcp_not_configured','The transit information service is temporarily unavailable.')
        return self.client.call_tool(name,arguments)

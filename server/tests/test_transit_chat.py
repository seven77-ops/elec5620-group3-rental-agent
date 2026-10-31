"""Conversation transport/state regression; model and MCP network are injected."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from server.tests import test_assistant_api as harness

class TransitChatTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def test_transit_followups_keep_brief_and_case_and_retries_do_not_repeat_tools(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Camperdown','max_weekly_rent':1000}}
        c=self.send(self.conversation()).json()
        home=next(r for r in c['messages'][-1]['listings'] if r['usyd_commute']['origin'])
        brief=deepcopy(c.get('rental_brief'));calls=[]
        def tool(provider,name,args):
            calls.append(name)
            return {'locations':[{'type':'stop','properties':{'STOP_NAME_WITH_PLACE':'Test stop','stopId':'2050123'},'distance':80}]} if name=='find_nearby' else {'alerts':[]}
        self.provider.result={'intent':'transit_info','transit_topic':'nearby','listing_ids':[home['listing_id']]}
        with patch('server.app.commute.mcp_transit.TransitProvider.tool',tool):
            response=self.send(c,'nearby','这套附近有什么车站',listing_ids=[home['listing_id']],allow_external_data=True)
            self.assertEqual(response.status_code,200,response.text)
            fresh=response.json();message=fresh['messages'][-1]
            self.assertEqual(message['transit_information']['listing_id'],home['listing_id'])
            self.assertFalse(message['listings']);self.assertFalse(message['actions'])
            self.assertEqual(self.send(c,'nearby','这套附近有什么车站',listing_ids=[home['listing_id']],allow_external_data=True).json(),fresh)
            self.assertEqual(calls,['find_nearby'])
            self.provider.result={'intent':'transit_info','transit_topic':'alerts','listing_ids':[home['listing_id']]}
            fresh=self.send(fresh,'alerts','现在有线路提醒吗',allow_external_data=True).json()
            self.assertEqual(fresh['messages'][-1]['transit_information']['topic'],'alerts')
            self.assertEqual(calls,['find_nearby','find_nearby','get_alerts'])
        self.assertEqual(fresh.get('rental_brief'),brief)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

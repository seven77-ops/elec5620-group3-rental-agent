"""Six fictional users against the actual model and API; no original-case writes.
Run from repository root with .venv/bin/python. Results are an observation record,
not an assertion that every model answer meets the intended product behavior.
"""
import concurrent.futures
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from scripts.local_ai_env import load_ai_env
from server.app.ai.provider import ModelProvider
from server.app.main import create_app

OUT=Path('docs/user-scenarios/2026-10-22')
ENV=load_ai_env('.env',os.environ)
PERSONAS=[
 {'id':'U01','name':'陈悦','role':'刚到悉尼的留学生','stage':'Agent1 需求澄清与 Agent2 检索',
  'requirements':'1人，Kensington，最高每人每周500澳元，独立房间，卧卫车位不限。首次表达故意遗漏预算单位。',
  'expectations':['主动澄清预算周期及计价对象','不将广告整套价格当成人均费用','未知账单和在租情况不冒充已核实'],
  'turns':['我是刚到悉尼的学生，想住Kensington附近，预算500。',
           '500是每人每周的最高预算，就我1个人，想租独立房间。卧室、浴室和车位数量都不限。',
           '先按Kensington查，预算保持最高每人每周500澳元。',
           '这些广告价格确定是每个人承担的，而且包水电网的吗？']},
 {'id':'U02','name':'周航和林薇','role':'共同租房的伴侣','stage':'Agent1 条件修改与 Agent2 比较',
  'requirements':'2人整租，Rhodes起步，2卧2卫，车位不限；预算从整套每周800提高到900，再扩大至Parramatta。',
  'expectations':['逐轮保留未修改条件','零结果时不虚构房源','比较真实广告并承认通勤和噪音数据缺失'],
  'turns':['我们2个人，想在Rhodes整租，最高每周800澳元，按整套算，要2卧2卫，车位不限。',
           '最高周租提高到900澳元，其他条件保持不变。',
           '区域改成Parramatta，最高仍是整套每周900澳元，2卧2卫，2个人整租，车位不限。',
           '把你展示的前两套比较一下，哪个广告周租更低？',
           '哪套最安静，坐火车到学校最快？']},
 {'id':'U03','name':'Alex Lin','role':'已有候选的上班族','stage':'Agent2 候选到 Agent3 草稿再到 Agent4 入住',
  'requirements':'已确认1人整租、Parramatta、2卧2卫、整套最高每周1500；选一条当前真实候选，使用虚构双方资料准备草稿。',
  'expectations':['候选之后给出可执行的询问入口','草稿保存不等于签约或入住','核对来源后才能带入住处与联系人'],
  'turns':['这套房子已经保存为候选了，下一步应该问中介什么？',
           '帮我生成这套房子的租约草稿。',
           '草稿已经生成了，是不是就算签约完成，可以自动当作已经入住？',
           '我已经在租后服务确认了实际住处，现在保存了哪些水电网络公司？']},
 {'id':'U04','name':'王晨','role':'入住后遇到维修问题的租客','stage':'Agent4 供应商记录和连续报修',
  'requirements':'已入住，电力AGL、网络TPG；厨房水槽漏水，需要邮件草稿、礼貌改写、记录中介回复并跟踪解决。',
  'expectations':['供应商选择经确认后同步','同一问题只保存一条报修','否定语句不能标记解决','邮件保持未发送'],
  'turns':['我的电力公司是AGL，网络用TPG，请帮我记下来。',
           '我现在用哪家电力和网络公司？',
           '厨房水槽下面一直漏水，帮我写一封报修邮件给中介。',
           '把这封邮件写得客气一点。',
           '中介回复说明天上午来修，帮我记录一下。',
           '现在还没修好，不要标记为解决。',
           '已经修好了，请把这条报修标记为已解决。',
           '这条报修现在是什么状态？']},
 {'id':'U05','name':'赵宁','role':'准备搬家退租的租客','stage':'Agent4 搬运清洁和未知价格',
  'requirements':'2026-12-15从Rhodes搬到Burwood；2卧2卫，有地毯和电梯；寻找搬运和退租清洁公司。',
  'expectations':['先保存本人明确提供的房屋和搬家条件','公司卡片链接来自真实目录','不编造报价、档期或押金保证'],
  'turns':['我在Rhodes，2卧2卫，有地毯，有电梯，2026-12-15搬走，搬到Burwood。请先帮我记录这些租后资料。',
           '根据我刚才说的条件，推荐几家悉尼搬家公司，给我网站或联系电话。',
           '再帮我找几家退租清洁公司，我需要清洁地毯。',
           '哪一家肯定最便宜，而且能保证把全部押金拿回来？']},
 {'id':'U06','name':'许然','role':'同时跟进两个维修问题的租客','stage':'Agent4 指代消歧与单条更新',
  'requirements':'同一住处已有厨房漏水和门锁损坏两条报修；有意使用“那个”和一句话多个问题来测试识别。',
  'expectations':['指代不明时询问具体问题','一句话涉及两条记录时不误改','明确问题后仅更新指定维修'],
  'turns':['那个问题处理好了，帮我标记解决。',
           '门锁损坏已经修好了，厨房漏水还没修好。',
           '那就只更新门锁损坏，标记为已解决。',
           '现在厨房漏水是什么状态？']}
]

class Run:
 def __init__(self,p):
  self.p=p;self.tmp=tempfile.TemporaryDirectory(prefix='rental-persona-')
  self.provider=ModelProvider(env=ENV)
  self.client=TestClient(create_app(runtime_dir=self.tmp.name,ai_provider=self.provider))
  self.case=self.ok(self.client.post('/api/v1/cases',json={}))
  self.root='/api/v1/cases/'+self.case['case_id'];self.living=self.root+'/living-services'
  self.chat=self.ok(self.client.post(self.root+'/assistant/conversations',json={}))
  self.path=self.root+'/assistant/conversations/'+self.chat['conversation_id']
  self.entries=[];self.checks=[];self.counter=0
 def ok(self,r):
  if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code}: {r.text[:400]}')
  return r.json()
 def post(self,path,data):return self.ok(self.client.post(path,json=data))
 def record(self):return self.ok(self.client.get(self.living))
 def state(self):
  v=self.record();c=self.ok(self.client.get(self.root))
  return {'living_version':v['version'],'profile':v['profile'],
   'repairs':[{'repair_id':r['repair_id'],'title':r['title'],'status':r['status'],'email_tone':r.get('email_tone'),
     'updates':r.get('updates',[]),'delivery_status':r['email']['delivery_status']} for r in v['repairs']],
   'booking_count':len(v['bookings']),'confirmation_versions':[x['version'] for x in c['confirmations']],
   'selected_listing':c.get('selection',{}).get('listing_id') if c.get('selection') else None,
   'aftercare_case_id':c.get('aftercare_case_id'),'tenancy_source':v.get('tenancy_source')}
 def op(self,label,details):self.entries.append({'type':'user_action','label':label,'details':details,'state':self.state()})
 def setup(self):
  if self.p['id']=='U03':
   c=self.case;profile=c['draft']['profile']
   profile['budget'].update(maximum=1500,scope='whole_property')
   profile.update(occupants=1,rental_mode='whole_property')
   profile.setdefault('housing_preferences',{}).update(suburb='Parramatta',min_bedrooms=2,min_bathrooms=2,min_car_spaces=0)
   c=self.post(self.root+'/profile-drafts',{'expected_revision':c['draft']['revision'],'profile':profile})
   c=self.post(self.root+'/profile-confirmations',{'draft_revision':c['draft']['revision'],'fingerprint':c['draft']['fingerprint'],'review_token':c['agent1']['review_token']})
   run=self.post(self.root+'/evaluations',{'request_id':'seed-report','confirmation_version':c['confirmations'][-1]['version']})
   rows=run['report']['pending_confirmation'] or run['report']['recommendations']
   self.post(self.root+'/selections',{'request_id':'seed-selection','run_id':run['run_id'],'listing_id':rows[0]['listing_id'],'confirmed':True})
   self.op('前置状态 已确认需求并保存一条真实广告候选',{'address':rows[0]['address'],'listing_id':rows[0]['listing_id'],'availability_verified':False})
  if self.p['id']=='U06':
   for n,title in enumerate(['厨房漏水','门锁损坏']):
    self.post(self.living+'/repairs',{'request_id':'seed-repair-'+str(n),'expected_version':n,'confirmed':True,
      'values':{'title':title,'description':title+'，用户记录待维修。','location':'厨房' if n==0 else '入户门','priority':'normal'}})
   self.op('前置状态 已保存两条待处理报修',{'issues':['厨房漏水','门锁损坏']})
 def send(self,text,i):
  before=self.state();started=time.monotonic()
  r=self.client.post(self.path+'/messages',json={'request_id':'turn-'+str(i),'expected_revision':self.chat['revision'],
       'message':text,'allow_external_ai':True})
  if r.status_code!=200:
   self.entries.append({'type':'dialogue','round':i+1,'user':text,'status':r.status_code,'error':r.json(),'elapsed_seconds':round(time.monotonic()-started,2)})
   return
  self.chat=r.json();a=self.chat['messages'][-1];after=self.state()
  self.entries.append({'type':'dialogue','round':i+1,'user':text,'status':200,'intent':a.get('intent'),'agent':a.get('agent'),
      'answer':a['content'],'actions':a.get('actions',[]),'listings':[{'listing_id':x['listing_id'],'address':x.get('address'),
      'bedrooms':x.get('bedrooms'),'bathrooms':x.get('bathrooms'),'weekly_rent':x.get('weekly_rent')} for x in a.get('listings',[])],
      'providers':[{k:x.get(k) for k in ('name','website','phone','categories')} for x in a.get('providers',[])],
      'model_calls':a.get('calls',[]),'elapsed_seconds':round(time.monotonic()-started,2),'state_before':before,'state_after':after})
  self.checks.append({'check':'本轮问答未自动改租后资料','round':i+1,'passed':before==after})
  print(json.dumps({'user':self.p['id'],'round':i+1,'intent':a.get('intent'),'proposals':len([x for x in a.get('actions',[]) if x['type'].startswith('apply_')])},ensure_ascii=False),flush=True)
  for action in a.get('actions',[]):
   if action['type']=='apply_preferences':
    result=self.post(self.root+'/assistant/proposals/'+action['proposal_id']+'/apply',{'request_id':'confirm-pref-'+str(i),'confirmed':True})
    self.chat=result['conversation']
    self.op('用户核对并点击确认偏好及生成候选',{'summary':action.get('summary',[]),'confirmation_version':self.chat.get('revision')})
   elif action['type']=='apply_living_services':
    # U04 deliberately rewrites the first repair draft before saving it.
    if self.p['id']=='U04' and i==2:continue
    result=self.post(self.living+'/proposals/'+action['proposal_id']+'/apply',{'request_id':'confirm-living-'+str(i),
      'expected_version':action['expected_version'],'confirmed':True})
    self.op('用户核对并点击确认保存租后资料或报修更新',{'summary':action.get('summary',[]),'version':result['version']})
  if self.p['id']=='U03' and i==1:self.contract_form()
  if self.p['id']=='U03' and i==2:self.import_home()
 def contract_form(self):
  context=self.ok(self.client.get(self.root+'/lease-drafts/context'))
  fields={**context['defaults'],'rental_mode':'whole_property','landlord_name':'Example Owner','landlord_contact':'owner@example.com',
    'landlord_notice_address':'1 Example Road, Sydney NSW 2000','tenant_names':'Alex Lin','tenant_contact':'alex@example.com',
    'agent_name':'Example Agent','agent_contact':'agent@example.com','lease_type':'fixed','start_date':'2026-11-01',
    'end_date':'2027-11-01','rent_amount':800,'rent_period':'week','bond':3200}
  draft=self.post(self.root+'/lease-drafts',{'request_id':'form-draft','context_token':context['context_token'],'expected_version':0,
    'confirmed':True,'applicability_confirmed':True,'fields':fields})
  pdf=self.client.get(self.root+'/lease-drafts/'+draft['draft_id']+'/pdf?version=1')
  self.op('用户在合同助手填写虚构双方资料并确认保存',{'draft_status':draft['status'],'draft_version':draft['version'],
   'fields':fields,'pdf_status':pdf.status_code,'pdf_header_ok':pdf.content.startswith(b'%PDF'),'creates_actual_tenancy':False})
 def import_home(self):
  preview=self.ok(self.client.get(self.living+'/tenancy-source'))
  fields=[k for k in ('address','agent_name','agent_email','lease_start_date','lease_end_date') if k in preview['values']]
  imported=self.post(self.living+'/tenancy-import',{'request_id':'import-home','expected_version':preview['expected_version'],
    'confirmed':True,'actual_tenancy_confirmed':True,'source_token':preview['source']['token'],'fields':fields})
  self.op('用户另行核实实际租约并确认接入住处资料',{'source_label':preview['source']['label'],'selected_fields':fields,
     'aftercare_case_created':False,'explanation':'只导入本人确认的资料，不自动创建退租押金案件，不证明签约。'})
 def run(self):
  try:
   self.setup()
   for i,text in enumerate(self.p['turns']):
    try:self.send(text,i)
    except Exception as exc:
     self.entries.append({'type':'operation_error','round':i+1,'error':str(exc)[:500]})
   final=self.state()
   return {'persona':self.p,'entries':self.entries,'checks':self.checks,'final_state':final,'method':'Actual model and API; user confirmation actions reproduced through API',
      'environment':'isolated temporary runtime','date':'2026-10-22'}
  finally:self.client.close();self.tmp.cleanup()


def main():
 OUT.mkdir(parents=True,exist_ok=True)
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(lambda p:Run(p).run(),p):p for p in PERSONAS}
  for future in concurrent.futures.as_completed(futures):
   p=futures[future]
   try:result=future.result()
   except Exception as exc:result={'persona':p,'fatal_error':str(exc)[:500]}
   results.append(result)
   (OUT/(p['id']+'-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 results.sort(key=lambda r:r['persona']['id'])
 (OUT/'simulation-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print(json.dumps({'completed':len(results),'turns':sum(sum(e['type']=='dialogue' for e in r.get('entries',[])) for r in results),
    'errors':sum(sum(e['type']=='operation_error' or e.get('status',200)!=200 for e in r.get('entries',[])) for r in results)},ensure_ascii=False),flush=True)

if __name__=='__main__':
 if len(sys.argv)>1:
  selected=next(p for p in PERSONAS if p['id']==sys.argv[1])
  result=Run(selected).run()
  OUT.mkdir(parents=True,exist_ok=True)
  (OUT/(selected['id']+'-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
  print(json.dumps({'completed_user':selected['id']},ensure_ascii=False))
 else:main()

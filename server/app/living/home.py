"""Read-only basic home handoff. Source values never silently confirm a tenancy."""
from copy import deepcopy
import re
from .service import LivingService
from .tenancy import LivingTenancy

BASIC_FIELDS=('address','suburb','postcode','agent_name','agent_email','agent_phone')
LOCATION=('address','suburb','postcode')
CONTACTS=('agent_name','agent_email','agent_phone')


def address_key(value):
    return ' '.join(re.sub(r'[,\s]+',' ',value or '').casefold().split())


class LivingHome:
    def __init__(self,ctx):
        self.ctx=ctx;self.living=LivingService(ctx);self.tenancy=LivingTenancy(ctx)

    def read(self,case_id:str):
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',case_id);record=self.living._record(db,case_id)
            profile=record['profile'];values={key:profile.get(key,'') for key in BASIC_FIELDS}
            sources={key:'Saved home details' for key in BASIC_FIELDS if values[key]}
            draft=self.tenancy._draft_source(db,case)
            selection=case.get('selection') or {}
            snapshot=selection.get('listing_snapshot') if selection.get('data_mode')=='real_listings' else None
            saved_location=any(values[key] for key in LOCATION)
            if not saved_location:
                source_values={};label=''
                if snapshot and snapshot.get('address'):
                    source_values={key:snapshot.get(key,'') for key in LOCATION};label='Selected property'
                else:
                    source=self.tenancy._aftercare_source(db,case)
                    if not source and draft and draft['current']:source=draft
                    if source:
                        source_values=deepcopy(source['values']);label=source['label']
                        fields=(source.get('basis') or {}).get('fields') or {}
                        for key in ('suburb','postcode'):
                            if fields.get(key):source_values[key]=fields[key]
                        if not source_values.get('postcode'):
                            postal=re.search(r'\bNSW\s*([0-9]{4})\b',source_values.get('address',''),re.I)
                            if postal:source_values['postcode']=postal.group(1)
                for key in LOCATION:
                    accepted=self.tenancy._accepted(key,source_values.get(key,''))
                    if key in accepted:values[key]=accepted[key];sources[key]=label
            # Saved contact groups remain intact, including deliberately blank fields.
            if not saved_location and not any(profile.get(key) for key in CONTACTS) and draft and draft['current']:
                draft_address=draft['values'].get('address','')
                shown=values['address']
                combined=', '.join(filter(None,(shown,' '.join(filter(None,(values['suburb'],'NSW',values['postcode']))))))
                if shown and address_key(draft_address) in {address_key(shown),address_key(combined)}:
                    for key in CONTACTS:
                        if draft['values'].get(key):values[key]=draft['values'][key];sources[key]='Saved lease draft'
            return {'values':values,'sources':sources,'profile':deepcopy(profile),'bookings':deepcopy(record['bookings']),'expected_version':record['version']}

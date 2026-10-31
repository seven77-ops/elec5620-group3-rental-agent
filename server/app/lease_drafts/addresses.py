"""Read-only suggestions from the existing NSW advertisement snapshot; no geocoding."""
import re
from ..common import require


def street_address(row):
    # Strip only the locality explicitly supplied by the source record. Unit/building
    # numbers are never parsed as postcodes and no missing street is synthesized.
    if re.fullmatch(re.escape(row['suburb'])+r'(?:\s+NSW)?(?:\s+'+re.escape(row['postcode'])+r')?',row['address'],re.I):return ''
    suffix=r'(?:,\s*|\s+)'+re.escape(row['suburb'])+r'(?:\s+NSW)?(?:\s+'+re.escape(row['postcode'])+r')?\s*$'
    return re.sub(suffix,'',row['address'],flags=re.I).strip().rstrip(',')


class LeaseAddresses:
    def __init__(self,ctx):self.ctx=ctx

    def search(self,q: str = ''):
        require(isinstance(q,str) and len(q)<=120,422,'invalid_address_query','Address searches may contain at most 120 characters.')
        query=q.strip().casefold()
        if len(query)<2:return {'items':[],'source':'local_catalog'}
        catalog=self.ctx.settings.catalog
        require(catalog is not None,503,'real_catalog_unavailable','The local NSW address catalogue is unavailable.')
        rows=catalog.matching({});localities={};addresses=[]
        for row in rows:
            suburb,postcode=row['suburb'],row['postcode']
            locality={'id':'locality:nsw:'+postcode+':'+re.sub(r'[^a-z0-9]+','-',suburb.casefold()).strip('-'),
                'kind':'locality','address':'','full_address':suburb+' NSW '+postcode,
                'suburb':suburb,'state':'NSW','postcode':postcode}
            localities[(suburb,postcode)]=locality
            address=street_address(row)
            if not address:continue
            item={'id':row['listing_id'],'kind':'address','address':address,
                'full_address':address+', '+suburb+' NSW '+postcode,
                'suburb':suburb,'state':'NSW','postcode':postcode,'source_url':row['source_url']}
            if any(query in value.casefold() for value in (item['full_address'],address,suburb,postcode)):
                addresses.append(item)
        matches=[item for item in localities.values() if query in item['full_address'].casefold() or
            re.search(r'(?<!\w)'+re.escape(item['suburb'])+r'(?!\w)',query,re.I)]
        matches.sort(key=lambda i:(i['suburb'].casefold()!=query,i['suburb'].casefold(),i['postcode']))
        addresses.sort(key=lambda i:(i['suburb'].casefold()!=query,i['full_address'].casefold(),i['id']))
        return {'items':(matches+addresses)[:10],'source':'local_catalog'}

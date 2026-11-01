"""Real-data intake and research routes; never invoke synthetic evaluation."""
from copy import deepcopy
from ..common import now, uid, shape, request_id, require
from .intake import validate_listing, freshness
from .market import MarketData


def register_real_data_routes(app, services):
    market = MarketData()
    provider = services.data_provider

    def config():
        return {'coverage': market.coverage(), 'providers': {**provider.public_config(),'transit':services.transit_provider.public_config()},
                'mode': 'real_data_research', 'formal_recommendation_enabled': False}

    def benchmark(postcode: str, bedrooms: int, rent_scope: str, weekly_rent: float | None = None):
        return market.lookup(postcode, bedrooms, rent_scope, weekly_rent)

    def read(case_id: str):
        with services.repo.transaction() as db:
            services.get(db, 'case', case_id)
            records = services.repo.get(db, 'real_listing_collection', case_id) or {'items': []}
        records = deepcopy(records)
        for row in records['items']:
            row['freshness'] = freshness(row['observed_at'])
        return records

    def save(case_id: str, body: dict):
        shape(body, ('request_id', 'listing'))
        key = case_id + ':' + request_id(body['request_id'])
        with services.repo.transaction() as db:
            services.get(db, 'case', case_id)
            old = services.receipt(db, 'real_listing_receipt', key, body)
            if old:
                return old['result']
            listing = validate_listing(body['listing'])
            records = services.repo.get(db, 'real_listing_collection', case_id) or {'items': []}
            require(len(records['items']) < 30, 409, 'listing_limit', 'This case can contain at most 30 live listing observations.')
            listing.update(record_id=uid('real'), saved_at=now())
            records['items'].append(listing)
            services.repo.put(db, 'real_listing_collection', case_id, records)
            services.save_receipt(db, 'real_listing_receipt', key, body, listing)
            return listing

    def export(case_id: str):
        return services.download({'case_id': case_id, 'mode': 'real_manual_unverified', **read(case_id)}, 'real-listings')

    app.get('/api/v1/real-data/config')(config)
    app.get('/api/v1/real-data/market')(benchmark)
    app.post('/api/v1/real-data/domain-search')(provider.search)
    app.post('/api/v1/real-data/trips')(provider.trips)
    app.get('/api/v1/cases/{case_id}/real-listings')(read)
    app.post('/api/v1/cases/{case_id}/real-listings')(save)
    app.get('/api/v1/cases/{case_id}/real-listings/export')(export)

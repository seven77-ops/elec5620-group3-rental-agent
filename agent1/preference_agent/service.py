"""UC01 and UC02. Confirmation is a separate, revision-bound UI operation."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4
from .bridge import fingerprint
from .fields import FIELDS, assess, validate_value
from .llm import ExtractionError, ManualOnly
from .store import dumps


def now():
    return datetime.now(timezone.utc).isoformat()


def new_draft(values=None, based_on=None):
    return {'draft_id': 'draft-' + uuid4().hex, 'revision': 0,
            'based_on_profile_version': based_on,
            'values': deepcopy(values or {}), 'issues': [], 'evidence': {}}


def active(session):
    if session['state'] == 'Cancelled':
        raise ValueError('Collection cancelled. Start a new case; no search was initiated.')


class ProfileService:
    def __init__(self, store):
        self.store = store

    def validateDraft(self, session):
        return assess(session['draft'], session['search_id'], session['latest_version'] + 1)

    def confirmAndSave(self, case_id, token, confirmed_by):
        if not isinstance(confirmed_by, str) or not confirmed_by.strip():
            raise ValueError('A nonempty local tenant label is required.')
        with self.store.transaction() as db:
            session, serial = self.store.load(case_id, db)
            active(session)
            review = session.get('review')
            if not review or token != review['token'] or review['revision'] != session['draft']['revision']:
                raise ValueError('Review is missing or stale. Run /review and confirm its current token.')
            result = self.validateDraft(session)
            if not result['valid']:
                raise ValueError('\n'.join(result['errors']))
            if fingerprint(result) != review['digest']:
                raise ValueError('Reviewed content changed. Review again.')
            version = session['latest_version'] + 1
            record = {'caseId': case_id, 'searchId': session['search_id'], 'profileVersion': version,
                      'confirmedBy': confirmed_by.strip(), 'confirmedAt': now(),
                      'sourceDraftId': session['draft']['draft_id'],
                      'reviewedDraftRevision': session['draft']['revision'],
                      'confirmationMethod': 'explicit_local_ui_action',
                      'profile': result['profile'], 'draftSnapshot': deepcopy(session['draft']),
                      'reviewWarnings': result['warnings']}
            db.execute('INSERT INTO profiles VALUES (?, ?, ?)', (case_id, version, dumps(record)))
            session.update(latest_version=version, state='Confirmed', review=None, latest_task_id=None)
            self.store.save(session, serial, db)
        return record

    def getConfirmed(self, case_id, version):
        return self.store.profile(case_id, version)


class PreferenceAgent:
    def __init__(self, store, llm):
        self.store, self.llm = store, llm
        self.profiles = ProfileService(store)

    def startCollection(self):
        case_id = 'case-' + uuid4().hex
        session = {'case_id': case_id, 'search_id': 'search-' + uuid4().hex,
                   'session_id': 'session-' + uuid4().hex,
                   'draft': new_draft(), 'state': 'AwaitingInitialInput', 'history': [],
                   'latest_version': 0, 'latest_task_id': None, 'review': None, 'last_error': None}
        self.store.create(session)
        return session

    def showDraft(self, case_id):
        session, _ = self.store.load(case_id)
        return session

    def _apply(self, session, updates, issues, source, message):
        # The entire response is checked before any field is changed.
        if not isinstance(updates, list) or not isinstance(issues, list):
            raise ExtractionError('updates and issues must be arrays.')
        json.dumps({'updates': updates, 'issues': issues}, allow_nan=False)
        seen = set()
        for item in updates:
            if not isinstance(item, dict) or set(item) != {'field', 'value', 'evidence'}:
                raise ExtractionError('Invalid update shape.')
            field = item['field']
            if not isinstance(field, str) or field in seen:
                raise ExtractionError('Invalid or duplicate field.')
            seen.add(field)
            validate_value(field, item['value'])
            if not isinstance(item['evidence'], str) or not item['evidence'] or item['evidence'] not in message:
                raise ExtractionError('Update evidence must quote the latest user input.')
        for item in issues:
            if not isinstance(item, dict) or set(item) != {'field', 'message', 'evidence'}:
                raise ExtractionError('Invalid issue shape.')
            if not isinstance(item['field'], str) or item['field'] not in FIELDS:
                raise ExtractionError('Unknown issue field.')
            if not isinstance(item['message'], str) or not item['message'].strip():
                raise ExtractionError('Missing clarification question.')
            if not isinstance(item['evidence'], str) or not item['evidence'] or item['evidence'] not in message:
                raise ExtractionError('Issue evidence must quote the latest user input.')
        if (session['latest_version'] and
                session['draft']['based_on_profile_version'] != session['latest_version'] and (updates or issues)):
            session['draft'] = new_draft(session['draft']['values'], session['latest_version'])
            session['state'] = 'AwaitingClarification'
        draft = session['draft']
        if updates or issues:
            draft['revision'] += 1
            for item in updates:
                draft['values'][item['field']] = deepcopy(item['value'])
                draft['evidence'][item['field']] = {'source': source, 'quote': item['evidence'], 'at': now()}
            draft['issues'] = [i for i in draft['issues'] if i['field'] not in seen]
            for item in issues:
                if item not in draft['issues']:
                    draft['issues'].append(deepcopy(item))
        session.update(review=None, last_error=None)
        result = self.profiles.validateDraft(session)
        if (not updates and not issues and session['latest_version'] and
                draft['based_on_profile_version'] != session['latest_version']):
            session['state'] = 'Confirmed'
        # A non-edit message cannot make a confirmed profile look like a new draft.
        if session['state'] != 'Confirmed':
            session['state'] = 'DraftReady' if result['valid'] else 'AwaitingClarification'
        reply = ('The draft is ready for review. Use /review; it has not been confirmed or submitted for a search.' if result['valid']
                 else '\n'.join(result['errors'][:4]))
        if session['state'] == 'Confirmed':
            reply = 'The confirmed preferences are unchanged. Use /search to run the local evaluation.'
        session['history'].extend([{'role': 'user', 'content': message}, {'role': 'assistant', 'content': reply}])
        return {'state': session['state'], 'reply': reply, **result}

    def processMessage(self, case_id, message):
        if not isinstance(message, str) or not message.strip() or len(message) > 20000:
            raise ValueError('Message must contain 1–20000 characters.')
        session, serial = self.store.load(case_id)
        active(session)
        if isinstance(self.llm, ManualOnly):
            # Unsupported offline text is not an attempted preference edit.
            # Preserve confirmations, review tokens and pending drafts exactly.
            return {'state': session['state'], 'valid': False,
                    'reply': 'Offline mode accepts commands only. Use /help or /set; preferences are unchanged.'}
        original = deepcopy(session)
        try:
            proposal = self.llm.extractRequirements(message, deepcopy(session['draft']), deepcopy(session['history']))
            if not isinstance(proposal, dict) or set(proposal) != {'updates', 'issues'}:
                raise ExtractionError('Unexpected model response fields.')
            result = self._apply(session, proposal['updates'], proposal['issues'], 'llm_candidate', message)
        except (ExtractionError, ValueError, TypeError) as exc:
            # Never save a partly processed draft or allow stale confirmation after an error.
            original.update(state='ProcessingError', review=None, last_error=str(exc))
            original['history'].append({'role': 'assistant', 'content': 'Input processing failed. The existing draft has been retained. Please retry.'})
            self.store.save(original, serial)
            return {'state': 'ProcessingError', 'reply': str(exc), 'valid': False, 'errors': [str(exc)]}
        self.store.save(session, serial)
        return result

    def recoverConfirmed(self, case_id):
        """Explicitly dismiss a failed input only when its draft is unchanged."""
        with self.store.transaction() as db:
            session, serial = self.store.load(case_id, db)
            active(session)
            if session['state'] != 'ProcessingError' or not session['latest_version']:
                raise ValueError('Recovery requires a processing error after confirmation.')
            record = self.store.profile(case_id, session['latest_version'], db)
            if session['draft'] != record['draftSnapshot']:
                raise ValueError('The draft contains revisions. Use /review and confirm those changes first.')
            session.update(state='Confirmed', review=None, last_error=None)
            session['history'].append({'role': 'user', 'content': '/recover-confirmed'})
            self.store.save(session, serial, db)
        return 'Failed input dismissed. The existing confirmed version is unchanged. Use /search.'

    def setFields(self, case_id, values):
        """Explicit manual correction, also usable when an LLM service fails."""
        if not isinstance(values, dict) or not values:
            raise ValueError('Expected a nonempty field/value object.')
        session, serial = self.store.load(case_id)
        active(session)
        message = json.dumps(values, ensure_ascii=False, allow_nan=False)
        updates = [{'field': k, 'value': v, 'evidence': message} for k, v in values.items()]
        result = self._apply(session, updates, [], 'manual_user_entry', message)
        self.store.save(session, serial)
        return result

    def reviewDraft(self, case_id):
        session, serial = self.store.load(case_id)
        active(session)
        if (session['latest_version'] and
                session['draft']['based_on_profile_version'] != session['latest_version']):
            raise ValueError('This draft is already confirmed. Change a field to create a new draft.')
        result = self.profiles.validateDraft(session)
        session['review'] = None
        if result['valid']:
            token = uuid4().hex[:16]
            session['review'] = {'token': token, 'revision': session['draft']['revision'], 'digest': fingerprint(result)}
            session['state'] = 'AwaitingConfirmation'
            result['confirmation_token'] = token
        else:
            session['state'] = 'AwaitingClarification'
        self.store.save(session, serial)
        return {'draft': deepcopy(session['draft']), **result}

    def confirmProfile(self, case_id, token, confirmed_by):
        return self.profiles.confirmAndSave(case_id, token, confirmed_by)

    def cancel(self, case_id):
        session, serial = self.store.load(case_id)
        session.update(state='Cancelled', review=None)
        self.store.save(session, serial)
        return 'Collection has stopped. Confirmed versions and history have been retained.'

    def reviseAfterNoMatch(self, case_id, task_id, accept=False):
        from .handover import verified_feedback
        session, serial = self.store.load(case_id)
        active(session)
        report = verified_feedback(self.store, session, task_id)
        if report['eligible']:
            raise ValueError('This result has eligible candidates; no-match revision does not apply.')
        failed = {}
        for row in report['excluded']:
            for name, check in row['hard_checks'].items():
                if check['status'] == 'fail':
                    failed[name] = failed.get(name, 0) + 1
        feedback = {
            'message': 'No confirmed eligible candidates were found in the supplied dataset. This does not show that no suitable properties exist in the wider rental market.',
            'pending_count': len(report['pending_confirmation']),
            'failed_check_counts': failed,
            'explanation': ('These are counts of failed checks among excluded listings. A listing may appear under several checks; the counts do not identify a single cause.' if failed
                            else 'The available feedback does not establish which conditions limited the results. The reason is unknown.'),
            'offer': 'Would you like to reconsider negotiable preferences first? Hard constraints require your explicit changes and renewed confirmation.',
            'revision_started': False}
        if accept:
            if session['state'] != 'Confirmed':
                raise ValueError('An unconfirmed draft already exists; finish or correct that draft first.')
            old = self.store.profile(case_id, session['latest_version'])
            session.update(draft=new_draft(old['draftSnapshot']['values'], session['latest_version']),
                           state='DraftReady', review=None)
            self.store.save(session, serial)
            feedback['revision_started'] = True
        return feedback

"""Read only local AI configuration, with no expansion, shell execution or overrides."""
from pathlib import Path
import shlex

ALLOWED={'RENTAL_AI_ENABLED','RENTAL_AI_URL','RENTAL_AI_MODEL','RENTAL_AI_API_KEY',
         'RENTAL_AI_TIMEOUT_SECONDS','AGENT3_MODEL_URL','AGENT3_MODEL_NAME','AGENT3_MODEL_API_KEY',
         'TFNSW_API_KEY','DOMAIN_API_KEY','DOMAIN_USE_APPROVED'}


def load_ai_env(path, environment):
    result=dict(environment)
    path=Path(path)
    if not path.is_file():
        return result
    for index,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        key,separator,value=line.partition('=')
        key=key.strip()
        if key not in ALLOWED or key in result:
            continue
        try:
            parts=shlex.split(value,comments=True,posix=True)
        except ValueError:
            raise ValueError(f'Invalid local AI configuration at line {index}') from None
        if not separator or len(parts)>1:
            raise ValueError(f'Invalid local AI configuration at line {index}')
        result[key]=parts[0] if parts else ''
    return result

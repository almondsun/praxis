import re
from .core import fetch_json


def check_updates(layout):
    result = []
    for name, current in layout.lock['components'].items():
        releases = fetch_json('https://api.github.com/repos/' + current['repository'] + '/releases?per_page=100')
        prefix = 'rust-v' if name == 'codex' else 'v'
        stable = [r for r in releases if not r['draft'] and not r['prerelease']
                  and re.fullmatch(re.escape(prefix) + r'\d+\.\d+\.\d+', r['tag_name'])]
        latest = max(stable, key=lambda r: tuple(map(int, r['tag_name'][len(prefix):].split('.')))) if stable else None
        result.append({'component': name, 'installed_pin': current['tag'],
                       'latest_stable': latest['tag_name'] if latest else None,
                       'release_notes': latest['html_url'] if latest else None})
    return {'updates': result, 'mutated': False,
            'next': 'Review release notes; update exact commits/artifact hashes in a working lockfile, bootstrap, self-test, then manually commit only after validation passes.'}

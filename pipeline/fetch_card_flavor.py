"""Every flavor text ever printed on an English Pokémon card, grouped by National Pokédex number.

Source: github.com/PokemonTCG/pokemon-tcg-data (the data behind api.pokemontcg.io; one JSON file per set,
far faster than paging the API). Writes card_flavor.json:
    {"25": [{"text": "...", "set": "Base", "date": "1999/01/09", "card": "base1-58", "name": "Pikachu"}, ...], ...}
build_pokemon.py prefers these over raw game entries: card editors already chose the good lines.

    cd pipeline
    python fetch_card_flavor.py
"""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = 'https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master/'
UA = {'User-Agent': 'PokemonSetLabels/1.0 (personal label printing)'}


def fetch(url):
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        except Exception as e:
            err = e; time.sleep(3 * (i + 1))
    raise err


sets = fetch(RAW + 'sets/en.json')


def cards_of(s):
    try:
        return s, fetch(RAW + 'cards/en/' + s['id'] + '.json')
    except Exception as e:
        print('FAIL', s['id'], e); return s, []


out, n_cards = {}, 0
with ThreadPoolExecutor(8) as ex:
    for s, cards in ex.map(cards_of, sets):
        for c in cards:
            n_cards += 1
            ft, nums = (c.get('flavorText') or '').strip(), c.get('nationalPokedexNumbers') or []
            if c.get('supertype') != 'Pokémon' or not ft or len(nums) != 1:   # tag teams etc. describe several species
                continue
            out.setdefault(str(nums[0]), []).append({'text': ft, 'set': s['name'], 'date': s.get('releaseDate', ''), 'card': c['id'], 'name': c['name']})
for v in out.values():
    v.sort(key=lambda x: x['date'])
json.dump(dict(sorted(out.items(), key=lambda kv: int(kv[0]))), open(os.path.join(HERE, 'card_flavor.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('%d sets, %d cards, %d species with card text, %d texts' % (len(sets), n_cards, len(out), sum(len(v) for v in out.values())))

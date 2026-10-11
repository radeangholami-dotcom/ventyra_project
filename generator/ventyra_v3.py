import argparse
from collections import Counter, defaultdict
import hashlib
import hmac
import os
import re
import secrets
import string
from dataclasses import dataclass

TEST_KEY = bytes.fromhex('14cebc68d86af9509f7a9fb90bc5341c5e75f99a4803ae96a586ff5ed5eaddcb')
CORPUS_TEXT = r'''Although ancient travelers remembered the ocean, distant islands questioned their stories.
Although curious strangers followed the rivers, restless dreamers discovered ancient secrets.
Although silent artists watched the clouds, courageous sailors discovered strange islands.
Although purple shadows followed the pilgrims, forgotten gardens sheltered distant kings.
While ancient sailors watched the islands, curious strangers questioned their stories.
While restless kings followed the river, silent dreamers remembered the ocean.
While distant travelers watched the clouds, ancient artists discovered curious secrets.
Because the strange islands remembered distant travelers, the sailors questioned them.
Because courageous kings discovered forgotten gardens, the artists followed them.
Because curious dreamers remembered ancient secrets, the travelers questioned them.
The ancient rivers startled curious pilgrims who were arguing over forgotten promises.
The distant clouds followed silent travelers who were quarreling over strange questions.
The restless mirrors questioned ancient artists who were arguing over curious blunders.
The silent islands discovered courageous sailors who were quarreling over distant memories.
The forgotten windows startled curious strangers arguing over ancient stories.
The strange gardens followed ancient kings quarreling over invisible secrets.
The purple shadows watched restless dreamers arguing over aromatic mistakes.
The courageous alders deflected devilish jerks quarreling over aromatic blunders.
The ancient islands were discovered by curious travelers while arguing over strange promises.
The restless sailors were followed by silent shadows while wandering beyond distant gardens.
The curious artists were startled by ancient mirrors while arguing over forgotten memories.
The silent windows, which ancient travelers remembered, watched the distant rivers.
The distant mirrors, which curious pilgrims discovered, followed the ancient clouds.
The forgotten gardens, which restless dreamers remembered, sheltered the silent travelers.
The ancient king, who remembered the restless ocean, discovered forgotten islands.
The curious traveler, who followed the distant river, questioned the silent sailor.
The strange dreamer, who watched the purple shadows, remembered ancient mistakes.
The distant islands remembered the ancient travelers; nevertheless, the sailors questioned them.
The curious artists discovered strange secrets; meanwhile, the distant shadows followed them.
The restless pilgrims remembered the forgotten gardens; however, the ancient kings questioned them.
The forgotten rivers watched the distant islands, but the silent sailors followed them.
The curious travelers discovered ancient gardens, and the strange kings questioned them.
The courageous artists remembered forgotten promises, yet the distant strangers questioned them.
The ancient dreamers, exhausted by distant journeys, discovered silent islands.
The curious pilgrims, confused by ancient warnings, followed the restless rivers.
The silent travelers, burdened by forgotten promises, questioned the strange kings.
When the ancient islands disappeared, the curious sailors remembered their homes.
When the distant shadows returned, the restless pilgrims discovered forgotten gardens.
When the strange rivers vanished, the courageous artists questioned the ancient kings.
The restless ocean, beyond which the distant sailors wandered, remembered forgotten promises.
The silent traveler discovered ancient secrets, although the curious kings questioned his story.
The strange islands remembered distant travelers, although the ancient dreamers had vanished.
Never had the curious travelers discovered such an ancient island.
Rarely had the silent king questioned the distant sailors.
The distant river remembered the ancient dreamer — and the restless ocean remained silent.
The purple shadows vanished; the ancient traveler remembered the curious island.'''
CODE_ALPHABET = string.ascii_uppercase + string.digits
VERSION = b'ventyra:syntax-markov-punctuation:v3:'
TOKEN_RE = re.compile(r"[a-z]+(?:['-][a-z]+)*|[.,;:!?]|[—]", re.I)
PUNCT = {',', ';', ':', '.', '!', '?', '—'}
POOLS = {
 'adj': ('ancient','silent','purple','invisible','forgotten','strange','distant',
         'restless','curious','courageous','aromatic','devilish'),
 'nature': ('alders','rivers','statues','mirrors','windows','islands','clouds',
            'engines','gardens','shadows','apples','pigeons'),
 'people': ('jerks','kings','artists','pilgrims','sailors','giants','travelers',
            'strangers','dreamers'),
 'abstract': ('blunders','mistakes','secrets','questions','echoes','memories',
              'stories','omens','promises'),
 'past_verb': ('deflected','startled','followed','discovered','watched','questioned'),
 'participle': ('quarreling','arguing'),
}
SYNTAXES = ('relative', 'participial', 'although', 'while', 'because',
            'passive', 'parenthetical', 'semicolon',
            'long_concessive', 'long_temporal')

def generate_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(8))

def code_hash(code, key):
    code = code.strip().upper()
    if not re.fullmatch('[A-Z0-9]{8}', code):
        raise ValueError('Code must have exactly 8 A-Z/0-9 characters')
    if len(key) != 32:
        raise ValueError('Master key must be exactly 32 bytes')
    return hmac.new(key, code.encode('ascii'), hashlib.sha256).hexdigest()

class HashStream:
    def __init__(self, root, label):
        self.key = hmac.new(root, VERSION + label.encode('ascii'), hashlib.sha256).digest()
        self.counter = 0
        self.buffer = b''

    def _uint64(self):
        if len(self.buffer) < 8:
            self.buffer += hmac.new(self.key, self.counter.to_bytes(8,'big'), hashlib.sha256).digest()
            self.counter += 1
        x, self.buffer = int.from_bytes(self.buffer[:8], 'big'), self.buffer[8:]
        return x

    def choose(self, weighted):
        items = [(item, int(weight)) for item, weight in weighted if weight > 0]
        if not items: raise ValueError('No possible choice')
        total = sum(weight for _, weight in items)
        limit = ((1 << 64) // total) * total
        if not limit: raise ValueError('Weights too large')
        while True:
            r = self._uint64()
            if r < limit: break
        pick = r % total
        for item, weight in items:
            if pick < weight: return item
            pick -= weight
        raise AssertionError('Selection error')

class Markov:
    def __init__(self, corpus_text):
        self.tri = defaultdict(Counter)
        self.bi = defaultdict(Counter)
        self.uni = Counter()
        self.punct_tri = defaultdict(Counter)
        self.punct_bi = defaultdict(Counter)
        self.punct_uni = Counter()
        self.training_sentences = 0
        for line in corpus_text.splitlines():
            tok = TOKEN_RE.findall(line.lower())
            if not tok: continue
            self.training_sentences += 1
            history = ['<s>','<s>']
            words_so_far = []
            for i,token in enumerate(tok):
                self.tri[tuple(history[-2:])][token] += 1
                self.bi[history[-1]][token] += 1
                self.uni[token] += 1
                history.append(token)
                if token not in PUNCT:
                    preceding = (words_so_far[-1] if words_so_far else '<s>', token)
                    next_token = tok[i+1] if i+1 < len(tok) else '.'
                    mark = next_token if next_token in PUNCT else '<none>'
                    self.punct_tri[preceding][mark] += 1
                    self.punct_bi[token][mark] += 1
                    self.punct_uni[mark] += 1
                    words_so_far.append(token)

    def word(self, state, choices, rng):
        choices = list(choices)
        prev2 = tuple(state[-2:])
        prev = state[-1]
        weights = [(w, 1 + self.uni[w] + 15*self.bi[prev][w] + 70*self.tri[prev2][w])
                   for w in choices]
        result = rng.choose(weights)
        state.append(result)
        return result

    def punctuation(self, lexical_words, legal_marks, rng):
        if not lexical_words: raise ValueError('Expected a word before punctuation')
        curr = lexical_words[-1]
        prev = lexical_words[-2] if len(lexical_words)>1 else '<s>'
        weighted = []
        for mark in legal_marks:
            global_count = self.punct_uni[mark]
            score = 2 + min(8,global_count) + 15*self.punct_bi[curr][mark] + 70*self.punct_tri[(prev,curr)][mark]
            if mark == '<none>':
                score = 3 + min(3,global_count//10) + 6*self.punct_bi[curr][mark] + 18*self.punct_tri[(prev,curr)][mark]
            weighted.append((mark,score))
        return rng.choose(weighted)

@dataclass(frozen=True)
class Unit:
    text: str
    boundary: str = 'inside'

def expand(syntax):
    subj = ['the','$adj_nature','$nature']
    people = ['the','$adj_people','$people']
    thing = ['the','$adj_abstract','$abstract']
    v, ing = '$past_verb', '$participle'
    if syntax == 'relative':
        stream = subj + [v] + people + ['who','were',ing,'over'] + thing
        return stream, {len(subj)+1+len(people)-1:'relative_boundary',len(stream)-1:'end'}
    if syntax == 'participial':
        stream = subj + [v] + people + [ing,'over'] + thing
        return stream, {len(subj)+1+len(people)-1:'participial_boundary',len(stream)-1:'end'}
    if syntax in ('although','while'):
        stream = [syntax.capitalize()] + people + ['were',ing,'over'] + thing
        split = len(stream)-1
        stream += subj + [v,'them']
        return stream, {split:'front_clause',len(stream)-1:'end'}
    if syntax == 'because':
        stream = subj + [v] + people
        split=len(stream)-1
        stream += ['because','they','were',ing,'over'] + thing
        return stream, {split:'causal_boundary',len(stream)-1:'end'}
    if syntax == 'passive':
        stream = people + ['were',v,'by'] + subj + ['while',ing,'over'] + thing
        return stream, {len(stream)-1:'end'}
    if syntax == 'parenthetical':
        stream = subj
        first=len(stream)-1
        stream += ['according','to'] + people
        second=len(stream)-1
        stream += [v] + thing + ['while',ing]
        return stream, {first:'appositive_open',second:'appositive_close',len(stream)-1:'end'}
    if syntax == 'semicolon':
        stream = subj + [v] + people
        first=len(stream)-1
        stream += ['meanwhile','they','were',ing,'over'] + thing
        return stream, {first:'independent',first+1:'after_connector',len(stream)-1:'end'}
    if syntax == 'long_concessive':
        stream = ['Although'] + people
        open_at=len(stream)-1
        stream += ['who','had','$past_verb2'] + thing
        close_at=len(stream)-1
        stream += ['were',ing,'over','the','$adj_abstract2','$abstract2']
        front_at=len(stream)-1
        stream += subj + [v,'them']
        independent_at=len(stream)-1
        stream += ['nevertheless','the','$adj_people2','$people2','remembered','their','warnings']
        return stream,{open_at:'appositive_open',close_at:'appositive_close',
                       front_at:'front_clause',independent_at:'independent',
                       independent_at+1:'after_connector',len(stream)-1:'end'}
    if syntax == 'long_temporal':
        stream=['When'] + subj
        open_at=len(stream)-1
        stream += ['which'] + people + ['had','$past_verb2']
        close_at=len(stream)-1
        stream += ['vanished']
        front_at=len(stream)-1
        stream += ['the','$adj_people2','$people2']
        rel_open=len(stream)-1
        stream += ['who','were',ing,'over']+thing
        rel_close=len(stream)-1
        stream += [v,'the','$adj_abstract2','$abstract2']
        return stream,{open_at:'appositive_open',close_at:'appositive_close',
                       front_at:'front_clause',rel_open:'appositive_open',
                       rel_close:'appositive_close',len(stream)-1:'end'}
    raise ValueError('Unknown syntax')

BOUNDARIES = {
 'inside': ('<none>',),
 'relative_boundary': ('<none>', ','),
 'participial_boundary': ('<none>', ','),
 'causal_boundary': ('<none>', ','),
 'front_clause': (',',),
 'appositive_open': (',',),
 'appositive_close': (',',),
 'independent': (';', '—'),
 'after_connector': (',',),
 'end': ('.',),
}

def generate(hash_hex, model, trace=False):
    if not re.fullmatch('[a-fA-F0-9]{64}', hash_hex):
        raise ValueError('Hash must contain 64 hex digits')
    root = bytes.fromhex(hash_hex)
    syntax_rng = HashStream(root,'syntax')
    word_rng = HashStream(root,'markov-words')
    punctuation_rng = HashStream(root,'markov-punctuation')
    syntax = syntax_rng.choose([(name,1) for name in SYNTAXES])
    token_plan, boundaries = expand(syntax)
    slot_pools = {
        'adj_nature':'adj', 'nature':'nature', 'past_verb':'past_verb',
        'adj_people':'adj', 'people':'people', 'participle':'participle',
        'adj_abstract':'adj', 'abstract':'abstract',
        'adj_abstract2':'adj','abstract2':'abstract','past_verb2':'past_verb',
        'adj_people2':'adj','people2':'people'
    }
    w = {}
    used_adjectives = set()
    state = ['<s>', '<s>']
    result=[]
    lexical_words=[]
    punctuation_events=[]
    for i, piece in enumerate(token_plan):
        if piece.startswith('$'):
            slot=piece[1:]
            pool=slot_pools[slot]
            candidates=[candidate for candidate in POOLS[pool]
                        if pool != 'adj' or candidate not in used_adjectives]
            raw=model.word(state,candidates,word_rng)
            w[slot]=raw
            if pool=='adj': used_adjectives.add(raw)
        else:
            raw=piece
            state.append(raw.lower())
        lexical_words.append(raw.lower())
        boundary=boundaries.get(i,'inside')
        mark=model.punctuation(lexical_words,BOUNDARIES[boundary],punctuation_rng)
        if mark!='<none>': state.append(mark)
        result.append(raw + ('' if mark=='<none>' else mark))
        punctuation_events.append((raw,boundary,mark))
    quote = ' '.join(result)
    quote = quote.replace('—',' —')
    quote = quote[0].upper() + quote[1:]
    return {'syntax':syntax, 'hash':hash_hex.lower(), 'selected_words':[w[slot] for slot in w],
            'quote':quote, 'punctuation_checks':len(punctuation_events),
            'punctuation_trace':punctuation_events if trace else None}

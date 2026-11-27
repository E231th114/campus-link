import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import app as board
from services.discussion import PRESETS, parse_deadline, reaction_state
from services.store import Local


class DiscussionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Local(temp.name)
        for ctx in (patch.object(board, 'store', self.store), patch.object(board, 'rate_limit')):
            ctx.start()
            self.addCleanup(ctx.stop)
        self.client = board.app.test_client()
        self.other = board.app.test_client()
        self.clock = patch.object(board, 'time').start()
        self.addCleanup(patch.stopall)
        self.clock.time.return_value = 1800000000
        self.path = self.send(self.client, '/post', message='旧データ互換', deadline_mode='1h').location
        self.key = self.path.split('/')[-1]

    def send(self, client, path, **fields):
        client.get('/')
        with client.session_transaction() as session:
            fields['csrf'] = session['csrf']
        return client.post(path, data=fields)

    def emoji(self, client, code='heart', active='1', revision=0):
        return self.send(client, self.path+'/emoji', emoji=code, active=active, revision=revision)

    def settings(self, **fields):
        return self.send(self.client, self.path+'/deadline', **fields)

    def test_dates(self):
        now = 1800000000
        for mode, seconds in PRESETS.items():
            self.assertEqual(parse_deadline(mode, '', now), now + seconds)
        self.assertEqual(parse_deadline('custom','2027-01-16T09:00',0), 1800057600)
        for mode, value in [('bad',''), ('custom','2020-01-01T12:00'), ('custom','tomorrow')]:
            self.assertEqual(self.settings(operation='set', deadline_mode=mode, deadline_custom=value).status_code,400)
        self.clock.time.return_value = now + 3599
        self.assertEqual(self.send(self.client,self.path+'/comment',message='直前').status_code,303)
        for offset in (3600,3601):
            self.clock.time.return_value = now + offset
            self.assertEqual(self.send(self.client,self.path+'/comment',message='期限外').status_code,409)
        self.assertIn('直前',self.client.get(self.path).text)
        self.assertEqual(self.emoji(self.other).status_code,200)
        self.assertEqual(self.send(self.other,self.path+'/like').status_code,303)
        self.assertEqual(self.send(self.other,self.path+'/deadline',operation='set').status_code,403)
        self.assertEqual(self.settings(operation='set',deadline_mode='3d').status_code,303)
        self.assertIn('回答受付中', self.client.get(self.path).text)
        self.settings(operation='pause')
        self.assertEqual(self.send(self.client,self.path+'/comment',message='停止').status_code,409)
        self.settings(operation='set',deadline_mode='none')
        self.assertEqual(self.send(self.client,self.path+'/comment',message='再開').status_code,303)
        self.send(self.client,self.path+'/resolved')
        self.settings(operation='set')
        self.assertEqual(self.send(self.client,self.path+'/comment',message='解決後').status_code,409)

    def test_expired_filter(self):
        self.assertIn(self.key,self.client.get('/?unanswered=on').text)
        self.clock.time.return_value += 3600
        self.assertNotIn(self.key,self.client.get('/?unanswered=on').text)

    def test_reactions(self):
        self.assertEqual(self.emoji(self.client,'thumb').status_code,400)
        self.assertEqual(self.client.post(self.path+'/emoji').status_code,403)
        self.assertEqual(self.emoji(self.client).json['heart']['count'],1)
        self.assertEqual(self.emoji(self.client).json['heart']['count'],1)
        self.assertEqual(self.emoji(self.other).json['heart']['count'],2)
        self.assertEqual(self.emoji(self.client,'idea').json['idea']['count'],1)
        self.assertFalse(self.emoji(self.client,active='0',revision=1).json['heart']['mine'])
        self.assertEqual(self.emoji(self.client).json['heart']['count'],1)
        self.assertEqual(self.store.rows('like'),[])
        self.assertIn('aria-label="共感した 1件"', self.other.get(self.path).text)
        self.send(self.client,self.path+'/deleted')
        self.assertEqual(self.emoji(self.other).status_code,404)

    def test_legacy_data_and_popularity(self):
        import uuid
        old_key = str(uuid.uuid4())
        self.store.add('board', old_key, {'name': '名無し', 'text': '旧投稿', 'posted_at': '2020/01/01'})
        self.store.add('like', old_key+'-legacy', {'post': old_key})
        self.emoji(self.client)
        self.emoji(self.other, 'clap')
        page = self.client.get('/?sort=popular').text
        self.assertLess(page.index('/p/'+old_key), page.index(self.path))
        detail = self.client.get('/p/'+old_key).text
        self.assertIn('参考になった 1',detail)
        self.assertIn('回答受付中',detail)
        self.assertNotIn('回答期限 20',detail)

    def test_reaction_rate(self):
        for revision in range(16):
            response = self.emoji(self.client, active=str(1-revision%2), revision=revision)
            self.assertEqual(response.status_code,200)
        self.assertEqual(self.emoji(self.client,revision=16).status_code,429)
        self.clock.time.return_value += 10
        self.assertEqual(self.emoji(self.client,revision=16).status_code,200)

    def test_concurrent_revision(self):
        def write(_):
            return self.store.add('emoji-'+self.key, 'owner-heart-1', dict(
                owner='owner', emoji='heart', active=True, revision=1, created=1800000000))
        with ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(write, range(16))),1)
        self.assertEqual(reaction_state(Local(self.store.root),self.key,'owner')['heart']['count'],1)

import tempfile
import unittest
import uuid
from unittest.mock import patch

import app
from services.emoji import POLICY, allowed_code
from services.store import Local


class ModerationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Local(directory.name)
        ctx = patch.object(app, 'store', self.db)
        ctx.start()
        self.addCleanup(ctx.stop)
        self.key = str(uuid.uuid4())
        self.db.add('board',self.key,dict(text='テスト',name='名無し',posted_at='2026/11/27'))
        self.path = '/p/' + self.key
        self.client = app.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.token = session['csrf']

    def react(self, glyph):
        return self.client.post(self.path+'/emoji',data=dict(csrf=self.token,emoji=glyph,active='1',revision=0))

    def test_blocked_inputs(self):
        for value in ('🖕','🖕🏿','🖕\ufe0f','🖕\ufe0e','🖕🏿\u200d👩','u-1f595','u-1f595-1f3ff','👩\u200d🖕'):
            self.assertEqual(self.react(value).status_code,400)
        self.assertEqual(self.db.rows('emoji-'+self.key),[])
        items=self.client.get(self.path+'/emoji-catalog').json['items']
        self.assertTrue(all('🖕' not in glyph for _,glyph,_,_ in items))
        for glyph in ('🍆','💉','👨🏾‍⚕️','🇯🇵','☪️','🦋'):
            self.assertEqual(self.react(glyph).status_code,200)
        self.assertEqual(allowed_code('♥️',self.key),allowed_code('♥',self.key))

    def test_hide_restore_and_report(self):
        self.assertEqual(self.react('❤️').json['heart']['count'],1)
        self.assertEqual(self.client.post(self.path+'/report',data=dict(csrf=self.token,reported_emoji='heart')).status_code,303)
        self.assertEqual(self.db.rows('report')[0]['emoji'],'heart')
        with patch.dict(POLICY['hidden_by_post'],{self.key:['heart']}):
            catalog=self.client.get(self.path+'/emoji-catalog').json
            self.assertNotIn('heart',catalog['recommended'])
            self.assertNotIn('heart',[row[0] for row in catalog['items']])
            self.assertNotIn('data-code="heart"',self.client.get(self.path).text)
            self.assertNotIn('heart',self.react('💡').json)
            self.assertEqual(self.react('heart').status_code,400)
        self.assertEqual(self.react('heart').json['heart']['count'],1)

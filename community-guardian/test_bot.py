import tempfile
import unittest
import time
from unittest.mock import patch
from bot import Bot

class FakeAPI:
    def __init__(self): self.calls=[]
    def call(self,method,**kw):
        self.calls.append((method,kw))
        if method=='getChatMember':
            return {'status':'creator' if kw['user_id']==1 else 'member'}
        if method=='getChat': return {'permissions':{'can_send_messages':True,'can_send_photos':False}}
        return {'message_id':99}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.api=FakeAPI(); self.path=self.tmp.name+'/db'
        self.bot=Bot(self.api,self.path)
    def tearDown(self): self.bot.db.close(); self.tmp.cleanup()
    def message(self,text,user=2,**kw):
        return {'chat':{'id':-100,'type':'supergroup','title':'Test'},'from':{'id':user},'text':text,'message_id':7,**kw}
    def test_nonadmin_cannot_configure(self):
        self.bot.message(self.message('/setrules hacked'))
        self.assertNotEqual(self.bot.config(-100)['rules'],'hacked')
    def test_settings_isolated_and_persist(self):
        self.bot.message(self.message('/setrules new rules',1))
        other=Bot(self.api,self.path)
        self.assertEqual(other.config(-100)['rules'],'new rules')
        self.assertNotEqual(other.config(-200)['rules'],'new rules'); other.db.close()
    def test_admin_target_protected(self):
        self.bot.message(self.message('/ban',1,reply_to_message={'from':{'id':1}}))
        self.assertFalse(any(c[0]=='banChatMember' for c in self.api.calls))
    def test_edited_hidden_link_deleted(self):
        cfg=self.bot.config(-100);cfg['links']=True;self.bot.save(-100,cfg)
        self.bot.handle({'edited_message':self.message('/anything',entities=[{'type':'text_link','url':'https://example.com'}])})
        self.assertTrue(any(c[0]=='deleteMessage' for c in self.api.calls))
    def test_warning_limit_mutes(self):
        for i in range(3):
            self.bot.message(self.message('/warn',1,reply_to_message={'from':{'id':2}}))
        self.assertTrue(any(c[0]=='restrictChatMember' for c in self.api.calls))
        self.assertIsNone(self.bot.db.execute('SELECT count FROM warnings').fetchone())
    def test_verification_bound_to_user_and_persists(self):
        cfg=self.bot.config(-100);cfg['captcha']=True;self.bot.save(-100,cfg)
        self.bot.message(self.message('',new_chat_members=[{'id':2,'first_name':'A'}]))
        nonce=self.bot.db.execute('SELECT nonce FROM pending').fetchone()[0]
        other=Bot(self.api,self.path)
        q={'id':'q','from':{'id':3},'message':{'chat':{'id':-100},'message_id':99},'data':'verify:'+nonce}
        other.callback(q)
        self.assertEqual(other.db.execute('SELECT count(*) FROM pending').fetchone()[0],1)
        q['from']['id']=2;other.callback(q)
        self.assertEqual(other.db.execute('SELECT count(*) FROM pending').fetchone()[0],0)
        calls=[kw for method,kw in self.api.calls if method=='restrictChatMember']
        self.assertFalse(calls[-1]['permissions']['can_send_photos']);other.db.close()
    def test_expired_verification_removed(self):
        self.bot.db.execute('INSERT INTO pending VALUES (?,?,?,?,?)',(-100,2,'n',time.time()-1,99));self.bot.db.commit()
        self.bot.expire()
        self.assertTrue(any(c[0]=='banChatMember' for c in self.api.calls))
        self.assertEqual(self.bot.db.execute('SELECT count(*) FROM pending').fetchone()[0],0)
    def test_flood_mutes(self):
        for i in range(6): self.bot.message(self.message('hello'))
        self.assertTrue(any(c[0]=='restrictChatMember' for c in self.api.calls))
    def test_filter_exact_match(self):
        self.bot.message(self.message('/filter website | https://example.com',1))
        self.bot.message(self.message('WEBSITE'))
        self.assertEqual(self.api.calls[-1][1]['text'],'https://example.com')

class DuplicateTests(Tests):
    def test_repeat_deleted_original_kept(self):
        self.bot.message(self.message('Hello   WORLD'))
        repeat=self.message('hello world');repeat['message_id']=8
        self.bot.message(repeat)
        deletes=[kw['message_id'] for method,kw in self.api.calls if method=='deleteMessage']
        self.assertEqual(deletes,[8])
    def test_other_member_and_group_allowed(self):
        self.assertFalse(self.bot.duplicate(-100,2,7,'hello'))
        self.assertFalse(self.bot.duplicate(-100,3,8,'hello'))
        self.assertFalse(self.bot.duplicate(-200,2,9,'hello'))
    def test_exact_boundary_and_no_sliding_window(self):
        with patch('bot.time.time',return_value=1000):
            self.assertFalse(self.bot.duplicate(-100,2,7,'hello'))
        with patch('bot.time.time',return_value=1119):
            self.assertTrue(self.bot.duplicate(-100,2,8,'hello'))
        with patch('bot.time.time',return_value=1120):
            self.assertFalse(self.bot.duplicate(-100,2,9,'hello'))
    def test_duplicate_survives_restart(self):
        self.bot.duplicate(-100,2,7,'hello')
        other=Bot(self.api,self.path)
        self.assertTrue(other.duplicate(-100,2,8,'hello'));other.db.close()
    def test_same_message_edit_not_deleted(self):
        self.assertFalse(self.bot.duplicate(-100,2,7,'hello'))
        self.assertFalse(self.bot.duplicate(-100,2,7,'HELLO'))
    def test_admin_exemption(self):
        self.bot.message(self.message('hello',1))
        m=self.message('hello',1);m['message_id']=8;self.bot.message(m)
        self.assertFalse(any(method=='deleteMessage' for method,_ in self.api.calls))
    def test_disable(self):
        self.bot.message(self.message('/duplicates off',1))
        self.bot.message(self.message('hello'))
        m=self.message('hello');m['message_id']=8;self.bot.message(m)
        self.assertFalse(any(method=='deleteMessage' for method,_ in self.api.calls))
    def test_caption_and_edited_repeat(self):
        self.bot.message(self.message('hello'))
        m=self.message('');del m['text'];m['caption']='hello';m['message_id']=8
        self.bot.handle({'edited_message':m})
        self.assertTrue(any(method=='deleteMessage' and kw['message_id']==8 for method,kw in self.api.calls))

if __name__=='__main__': unittest.main()

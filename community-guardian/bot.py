"""Community Guardian. Python 3.11+, standard library only."""
import collections
import hashlib
import unicodedata
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path

LOG = logging.getLogger('guardian')
DEFAULT = dict(rules='Be respectful. No spam or scams.', welcome='Welcome {name} to {group}! Use /rules.', captcha=False, links=False, flood=True, duplicates=True, warnlimit=3, filters={}, blocked=[])
HELP = '''Community Guardian
Everyone: /rules /help /id
Admins:
/setrules Your rules
/setwelcome Welcome {name} to {group}!
/filter keyword | automatic reply
/unfilter keyword
/blockword word   /unblockword word
/captcha on|off   /links on|off   /flood on|off
/duplicates on|off (same member, same text, 120 seconds)
/warnlimit 3   /settings
Reply to a member's message:
/warn /warnings /resetwarns /mute 30 /unmute /ban /kick /unban
Mute duration is in minutes (1–43200). Warning limit triggers a 60-minute mute.
CAPTCHA is a simple 120-second button check; it does not guarantee a human.
'''

class APIError(Exception):
    pass

class Telegram:
    def __init__(self, token):
        self.url = 'https://api.telegram.org/bot' + token + '/'
    def call(self, method, **data):
        req = urllib.request.Request(self.url + method, json.dumps(data).encode(), {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                result = json.load(response)
        except urllib.error.HTTPError as e:
            try:
                result = json.loads(e.read())
            except Exception:
                raise APIError('Telegram HTTP error') from None
        except (OSError, ValueError):
            raise APIError('Telegram connection failed') from None
        if not result.get('ok'):
            raise APIError(result.get('description', 'Telegram error'))
        return result['result']

class Bot:
    def __init__(self, api, path='data/guardian.sqlite3'):
        self.api = api
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS settings(chat INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS warnings(chat INTEGER, user INTEGER, count INTEGER, PRIMARY KEY(chat,user));
        CREATE TABLE IF NOT EXISTS pending(chat INTEGER,user INTEGER,nonce TEXT,expires REAL,message INTEGER,PRIMARY KEY(chat,user));
        CREATE TABLE IF NOT EXISTS duplicates(chat INTEGER,user INTEGER,digest TEXT,message INTEGER,seen REAL,PRIMARY KEY(chat,user,digest));
        CREATE INDEX IF NOT EXISTS duplicates_seen ON duplicates(seen);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value INTEGER);''')
        self.flood = {}
        self.username = ''
    def config(self, chat):
        row = self.db.execute('SELECT value FROM settings WHERE chat=?', (chat,)).fetchone()
        return {**json.loads(json.dumps(DEFAULT)), **(json.loads(row[0]) if row else {})}
    def save(self, chat, cfg):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (chat,json.dumps(cfg)))
    def say(self, chat, text, **kw):
        return self.api.call('sendMessage', chat_id=chat, text=text[:4000], **kw)
    def admin(self, chat, user, right=None):
        member = self.api.call('getChatMember', chat_id=chat,user_id=user)
        return member['status']=='creator' or (member['status']=='administrator' and (right is None or member.get(right,False)))
    def restrict(self, chat, user, minutes=60):
        self.api.call('restrictChatMember',chat_id=chat,user_id=user, permissions={'can_send_messages':False},until_date=int(time.time())+minutes*60)
    def restore(self, chat, user):
        perms = self.api.call('getChat',chat_id=chat).get('permissions')
        if not perms:
            raise APIError('Unable to read default group permissions')
        self.api.call('restrictChatMember',chat_id=chat,user_id=user,permissions=perms,use_independent_chat_permissions=True)
    def cleanup(self, chat, message):
        if message:
            try:
                self.api.call('deleteMessage',chat_id=chat,message_id=message)
            except APIError:
                pass
    def expire(self):
        for chat,user,nonce,expires,message in self.db.execute('SELECT * FROM pending WHERE expires<=?',(time.time(),)).fetchall():
            try:
                # Temporary ban removes the member and allows them to try again later.
                self.api.call('banChatMember',chat_id=chat,user_id=user,until_date=int(time.time())+60)
                with self.db:
                    self.db.execute('DELETE FROM pending WHERE chat=? AND user=?',(chat,user))
                self.cleanup(chat,message)
            except APIError:
                LOG.warning('Verification timeout action failed in chat %s; will retry',chat)
    def callback(self, q):
        message = q.get('message',{})
        chat = message.get('chat',{}).get('id')
        user = q['from']['id']
        row = self.db.execute('SELECT nonce,expires,message FROM pending WHERE chat=? AND user=?',(chat,user)).fetchone()
        if not row or q.get('data')!='verify:'+row[0] or row[1]<=time.time() or row[2]!=message.get('message_id'):
            self.api.call('answerCallbackQuery',callback_query_id=q['id'],text='This verification is not yours or has expired.')
            return
        self.restore(chat,user)
        with self.db:
            self.db.execute('DELETE FROM pending WHERE chat=? AND user=?',(chat,user))
        self.api.call('answerCallbackQuery',callback_query_id=q['id'],text='Verified!')
        self.cleanup(chat,row[2])
    def warn(self, chat, user, cfg):
        with self.db:
            self.db.execute('INSERT INTO warnings VALUES (?,?,1) ON CONFLICT(chat,user) DO UPDATE SET count=count+1',(chat,user))
        count = self.db.execute('SELECT count FROM warnings WHERE chat=? AND user=?',(chat,user)).fetchone()[0]
        if count>=cfg['warnlimit']:
            self.restrict(chat,user)
            with self.db:
                self.db.execute('DELETE FROM warnings WHERE chat=? AND user=?',(chat,user))
            self.say(chat,f'Member {user}: warning limit reached; muted for 60 minutes.')
        else:
            self.say(chat,f'Member {user}: warning {count}/{cfg["warnlimit"]}.')
    def duplicate(self, chat, user, message, text):
        normalized=' '.join(unicodedata.normalize('NFKC',text).casefold().split())
        if not normalized:
            return False
        digest=hashlib.sha256(normalized.encode()).hexdigest()
        now=time.time()
        with self.db:
            self.db.execute('DELETE FROM duplicates WHERE seen<=?',(now-120,))
            row=self.db.execute('SELECT message FROM duplicates WHERE chat=? AND user=? AND digest=?',(chat,user,digest)).fetchone()
            if row and row[0]!=message:
                return True
            # Replayed updates or edits to the same message do not extend its window.
            self.db.execute('INSERT OR IGNORE INTO duplicates VALUES (?,?,?,?,?)',(chat,user,digest,message,now))
        return False

    def message(self, m):
        chat=m['chat']['id']; user=m.get('from',{}).get('id')
        text=m.get('text',m.get('caption',''))
        if m['chat']['type']=='private':
            if text.startswith(('/start','/help')):
                self.say(chat,HELP+'\nAdd me as an admin to a supergroup to begin.')
            return
        if m['chat']['type']!='supergroup':
            if text.startswith('/help'):
                self.say(chat,'Use a Telegram supergroup for moderation features.')
            return
        cfg=self.config(chat)
        for member in m.get('new_chat_members',[]):
            if member.get('is_bot'):
                continue
            name=member.get('first_name','member')
            welcome=cfg['welcome'].replace('{name}',name).replace('{group}',m['chat'].get('title','the group'))
            if cfg['captcha']:
                self.restrict(chat,member['id'],3)
                nonce=secrets.token_hex(10)
                # Persist before sending so a failed send still has timeout recovery.
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO pending VALUES (?,?,?,?,NULL)',(chat,member['id'],nonce,time.time()+120))
                sent=self.say(chat,welcome+'\n'+name+': tap Verify within 120 seconds.',reply_markup={'inline_keyboard':[[{'text':'Verify','callback_data':'verify:'+nonce}]]})
                with self.db:
                    self.db.execute('UPDATE pending SET message=? WHERE chat=? AND user=?',(sent['message_id'],chat,member['id']))
            else:
                self.say(chat,welcome)
        if not user or m.get('sender_chat') or m.get('from',{}).get('is_bot'):
            return
        isadmin=self.admin(chat,user)
        # Enforce filters even on slash commands from regular members.
        if not isadmin:
            if cfg['duplicates'] and self.duplicate(chat,user,m['message_id'],text):
                self.api.call('deleteMessage',chat_id=chat,message_id=m['message_id'])
                return
            entities=m.get('entities',[])+m.get('caption_entities',[])
            haslink=any(e['type'] in ('url','text_link') for e in entities) or bool(re.search(r'(?:https?://|www\.|t\.me/)',text,re.I))
            blocked=any(re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',text,re.I) for w in cfg['blocked'])
            now=time.time(); key=(chat,user)
            recent=self.flood.setdefault(key,collections.deque())
            while recent and recent[0]<now-10:
                recent.popleft()
            recent.append(now)
            if len(self.flood)>10000:
                self.flood={k:v for k,v in self.flood.items() if v and v[-1]>now-60}
            if (cfg['links'] and haslink) or blocked or (cfg['flood'] and len(recent)>5):
                self.api.call('deleteMessage',chat_id=chat,message_id=m['message_id'])
                if cfg['flood'] and len(recent)>5:
                    self.restrict(chat,user,5)
                    recent.clear()
                return
        if text.startswith('/'):
            head,_,arg=text.partition(' '); cmd,_,address=head[1:].partition('@'); cmd=cmd.lower(); arg=arg.strip()
            if address and address.lower()!=self.username.lower():
                return
            if cmd in ('start','help','rules','id'):
                self.say(chat, cfg['rules'] if cmd=='rules' else f'Chat: {chat}\nYour ID: {user}' if cmd=='id' else HELP)
                return
            commands={'setrules','setwelcome','filter','unfilter','blockword','unblockword','captcha','links','flood','duplicates','warnlimit','settings','warn','warnings','resetwarns','mute','unmute','ban','kick','unban'}
            if cmd not in commands:
                return
            if not isadmin:
                self.say(chat,'Only group admins can use this command.'); return
            right='can_restrict_members' if cmd in {'warn','resetwarns','mute','unmute','ban','kick','unban','captcha','warnlimit'} else 'can_change_info'
            if not self.admin(chat,user,right):
                self.say(chat,'Your admin role does not have the permission needed for this command.'); return
            if cmd=='settings':
                self.say(chat,json.dumps(cfg,indent=2)); return
            if cmd in ('setrules','setwelcome'):
                if not arg or len(arg)>3000:
                    self.say(chat,'Provide text between 1 and 3000 characters.'); return
                cfg['rules' if cmd=='setrules' else 'welcome']=arg
            elif cmd in ('captcha','links','flood','duplicates'):
                if arg not in ('on','off'):
                    self.say(chat,'Use on or off.'); return
                cfg[cmd]=arg=='on'
            elif cmd=='warnlimit':
                if not arg.isdigit() or not 1<=int(arg)<=20:
                    self.say(chat,'Choose a warning limit from 1 to 20.'); return
                cfg['warnlimit']=int(arg)
            elif cmd=='filter':
                key,sep,value=arg.partition('|'); key=key.strip().casefold(); value=value.strip()
                if not sep or not key or not value or len(key)>100 or len(value)>3000:
                    self.say(chat,'Use /filter keyword | reply (keyword ≤100, reply ≤3000 characters).'); return
                cfg['filters'][key]=value
            elif cmd=='unfilter':
                cfg['filters'].pop(arg.casefold(),None)
            elif cmd in ('blockword','unblockword'):
                word=arg.casefold()
                if not word or len(word)>100:
                    self.say(chat,'Provide a word or phrase up to 100 characters.'); return
                cfg['blocked']=list(set(cfg['blocked']+[word])) if cmd=='blockword' else [w for w in cfg['blocked'] if w!=word]
            else:
                target=m.get('reply_to_message',{}).get('from',{})
                uid=target.get('id')
                if not uid or m.get('reply_to_message',{}).get('sender_chat'):
                    self.say(chat,'Reply to a member’s message to use this command.'); return
                if target.get('is_bot') or self.admin(chat,uid):
                    self.say(chat,'Bot and admin accounts are protected.'); return
                if cmd=='warn':
                    self.warn(chat,uid,cfg); return
                if cmd=='warnings':
                    row=self.db.execute('SELECT count FROM warnings WHERE chat=? AND user=?',(chat,uid)).fetchone()
                    self.say(chat,f'Warnings: {row[0] if row else 0}'); return
                if cmd=='resetwarns':
                    with self.db:
                        self.db.execute('DELETE FROM warnings WHERE chat=? AND user=?',(chat,uid))
                elif cmd=='mute':
                    if arg and (not arg.isdigit() or not 1<=int(arg)<=43200):
                        self.say(chat,'Use /mute 1–43200 (minutes).'); return
                    self.restrict(chat,uid,int(arg or 60))
                elif cmd=='unmute':
                    self.restore(chat,uid)
                    with self.db:
                        self.db.execute('DELETE FROM pending WHERE chat=? AND user=?',(chat,uid))
                elif cmd=='unban':
                    self.api.call('unbanChatMember',chat_id=chat,user_id=uid,only_if_banned=True)
                else:
                    self.api.call('banChatMember',chat_id=chat,user_id=uid)
                    if cmd=='kick':
                        self.api.call('unbanChatMember',chat_id=chat,user_id=uid,only_if_banned=True)
                self.say(chat,'Done.'); return
            self.save(chat,cfg); self.say(chat,'Setting saved.'); return
        reply=cfg['filters'].get(text.strip().casefold())
        if reply:
            self.say(chat,reply)
    def handle(self, update):
        if 'callback_query' in update:
            self.callback(update['callback_query'])
        elif 'message' in update or 'edited_message' in update:
            self.message(update.get('message',update.get('edited_message')))
    def run(self):
        me=self.api.call('getMe'); self.username=me['username']
        # Do not silently disrupt a webhook deployment of this token.
        if self.api.call('getWebhookInfo').get('url'):
            raise SystemExit('This token has a webhook. Remove it before running polling, or use a new bot token.')
        LOG.info('Started @%s',self.username)
        row=self.db.execute("SELECT value FROM meta WHERE key='offset'").fetchone(); offset=row[0] if row else 0
        while True:
            try:
                self.expire()
                updates=self.api.call('getUpdates',offset=offset,timeout=10,allowed_updates=['message','edited_message','callback_query'])
                for update in updates:
                    try:
                        self.handle(update)
                    except APIError as e:
                        LOG.warning('Telegram action failed: %s',str(e))
                        m=update.get('message',{})
                        if m.get('text','').startswith('/'):
                            try:
                                self.say(m['chat']['id'],'Action failed. Check bot permissions and try again.')
                            except APIError:
                                pass
                    except Exception:
                        LOG.error('Update failed; review configuration and restart if repeated.')
                    offset=update['update_id']+1
                    with self.db:
                        self.db.execute("INSERT OR REPLACE INTO meta VALUES ('offset',?)",(offset,))
            except APIError as e:
                LOG.warning('Polling/recovery failed: %s',str(e)); time.sleep(5)

def load_env():
    if Path('.env').exists():
        for line in Path('.env').read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1); os.environ.setdefault(key.strip(),value.strip().strip('\"\''))

if __name__=='__main__':
    load_env()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    token=os.environ.get('BOT_TOKEN','')
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):
        raise SystemExit('Set BOT_TOKEN in .env first. See README.md.')
    Bot(Telegram(token),os.environ.get('DB_PATH','data/guardian.sqlite3')).run()

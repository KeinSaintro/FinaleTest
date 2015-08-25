#!/usr/bin/env python
# -*- coding: ascii -*-

import os.path

import sqlite3
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.auth
import tornado.gen
import tornado.options
from tornado import gen
from tornado.options import define
from tornado.escape import json_decode, json_encode

# from tornado.options import define, options, parse_command_line
define("google_oauth", default={"key": "", "secret": ""}, help="google oauth")

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/', MainHandler),
            (r'/login', GoogleLoginHandler),
            (r'/fblogin', FBLoginHandler),
            (r'/logout', LogoutHandler),
            (r'/create', CreateHandler),
            (r'/save', SaveHandler),
            (r'/saveview', SaveViewHandler),
            (r'/view/([0-9]+)', ViewHandler),
            (r'/list', ListHandler),
            (r'/stats/([0-9]+)', StatHandler),
        ]
        settings = dict(
            cookie_secret="your_cookie_secret",
            template_path=os.path.join(os.path.dirname(__file__), 'templates'),
            static_path=os.path.join(os.path.dirname(__file__), 'static'),
            google_consumer_key='879896045870-l8cdpfqhtq3g9hgl8rli568pk4bfk5kr.apps.googleusercontent.com',
            google_consumer_secret='MNvexU-Yo8RKOLHucGE8nqEr',
            google_oauth = dict(key="879896045870-l8cdpfqhtq3g9hgl8rli568pk4bfk5kr.apps.googleusercontent.com", secret ="MNvexU-Yo8RKOLHucGE8nqEr"),
            facebook_api_key='123692397976839',
            facebook_secret='2390e63b74a313aa54e444e92d09de5c',
            login_url='/',
            xsrf_cookies=False,
            debug=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie('username')
        if not user_json:
            return None
        return json_decode(user_json)


class MainHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect('/create')
        self.render('index.html')


class GoogleLoginHandler(tornado.web.RequestHandler, tornado.auth.GoogleOAuth2Mixin):
    @tornado.gen.coroutine
    def get(self):
        if self.get_argument('code', False):
            access = yield self.get_authenticated_user(
                redirect_uri='http://protected-brook-2075.herokuapp.com/login',
                code=self.get_argument('code'))
            user = yield self.oauth2_request(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                access_token=access["access_token"])
            self.set_secure_cookie('username', json_encode(user))
            self.redirect("/create")
        else:
            yield self.authorize_redirect(
                redirect_uri='http://localhost:8000/login',
                client_id=self.settings['google_oauth']['key'],
                scope=['https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/plus.login'],
                response_type='code',
                extra_params={'approval_prompt': 'auto'})


class FBLoginHandler(tornado.web.RequestHandler, tornado.auth.FacebookGraphMixin):
    @tornado.gen.coroutine
    def get(self):
        if self.get_argument("code", False):
            user = yield self.get_authenticated_user(
                redirect_uri='http://protected-brook-2075.herokuapp.com/fblogin',
                client_id=self.settings["facebook_api_key"],
                client_secret=self.settings["facebook_secret"],
                code=self.get_argument("code"))
            self.set_secure_cookie('username', json_encode(user))
            self.redirect("/create")
        else:
            yield self.authorize_redirect(
                redirect_uri='http://protected-brook-2075.herokuapp.com/fblogin',
                client_id=self.settings["facebook_api_key"],
                extra_params={"scope": "email, public_profile"})


class LogoutHandler(tornado.web.RequestHandler):
    def get(self):
        self.clear_all_cookies()
        self.redirect("/")


class CreateHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('create.html', user=self.current_user)


class SaveHandler(BaseHandler):
    @tornado.web.authenticated
    @gen.coroutine
    def post(self):
        conn = sqlite3.connect('Test')
        c = conn.cursor()
        cursor = self.get_argument("ans", None)
        if cursor:
            cursor = json_decode( cursor )
            cursor.reverse()
            head = cursor.pop()
            head = head.split(" ")
            _text = ' '.join(head[1:]).encode('utf-8')
            insert = (_text,)
            c.execute("INSERT INTO inter (text) VALUES (?)", insert)
            while cursor:
                some = cursor.pop()
                some = some.split(" ")
                _text = ' '.join(some[1:]).encode('utf-8')
                if some[0] == 'vot':
                    c.execute('SELECT idinter FROM inter ORDER BY idinter DESC LIMIT 1')
                    maxid = c.fetchone()
                    insert = (maxid[0], _text, False,)
                    c.execute("INSERT INTO voting (interid,text,ch) VALUES (?,?,?)", insert )
                elif some[0] =='ch':
                    c.execute('SELECT idvoting FROM voting ORDER BY idvoting DESC LIMIT 1')
                    maxid = c.fetchone()
                    insert = (maxid[0],)
                    c.execute('UPDATE voting SET ch = 1 WHERE idvoting=?', insert)
                else:
                    c.execute('SELECT idvoting FROM voting ORDER BY idvoting DESC LIMIT 1')
                    maxid = c.fetchone()
                    insert = (maxid[0], _text, 0,)
                    c.execute("INSERT INTO answer (votingid,text,colans) VALUES (?,?,?)", insert)
            conn.commit()
            conn.close()
            self.redirect("/list")


class ListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        conn = sqlite3.connect('Test')
        c = conn.cursor()
        conn.commit()
        c.execute('SELECT * FROM inter')
        rows = c.fetchall()
        for row in rows:
                self.write('<a href="http://localhost:8000/view/'+ str(row[0]) + '"> ' + row[1].encode('cp1251')+' </a><br><br>')
        self.render('list.html', user=self.current_user)
        conn.close()


class ViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,interid):
        conn = sqlite3.connect('Test')
        c = conn.cursor()
        insert = (self.current_user['id'], interid)
        c.execute('SELECT * FROM author WHERE author=? AND interid =?', insert)
        postans = c.fetchone()
        if postans:
            link = '/stats/' + interid
            self.redirect(link)
        _ans = []
        insert = (interid,)
        c.execute('SELECT text FROM inter WHERE idinter=?', insert)
        _title = c.fetchone()
        c.execute('SELECT * FROM voting WHERE interid=?', insert)
        _vot = c.fetchall()
        for votid in _vot:
            insert = (votid[0],)
            c.execute('SELECT idans,votingid,text FROM answer WHERE votingid=?', insert)
            _ans.append(c.fetchall())
        self.render('view.html', _title=_title, _vot = _vot, _ans = _ans, interid = interid)
        conn.commit()
        conn.close()


class StatHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,interid):
        conn = sqlite3.connect('Test')
        c = conn.cursor()
        insert = (self.current_user['id'], interid)
        c.execute('SELECT * FROM author WHERE author=? AND interid =?', insert)
        postans = c.fetchone()
        if not postans:
            link = '/view/' + interid
            self.redirect(link)
        _ans = []
        insert = (interid,)
        c.execute('SELECT text FROM inter WHERE idinter=?', insert)
        _title = c.fetchone()
        c.execute('SELECT * FROM voting WHERE interid=?', insert)
        _vot = c.fetchall()
        for votid in _vot:
            insert = (votid[0],)
            c.execute('SELECT text, colans FROM answer WHERE votingid=?', insert)
            _ans.append(c.fetchall())
        self.render('stats.html', _title=_title, _vot = _vot, _ans = _ans)
        conn.commit()
        conn.close()


class SaveViewHandler(BaseHandler):
    @tornado.web.authenticated
    @gen.coroutine
    def post(self):
        conn = sqlite3.connect('Test')
        c = conn.cursor()
        cursor = self.get_argument("ans", None)
        interid = self.get_argument("interid",None)
        if cursor:
            cursor = json_decode( cursor )
            for i in cursor:
                insert = (int(i),)
                c.execute('SELECT colans FROM answer WHERE idans=?', insert)
                postcol = c.fetchone()
                postpostcol = postcol[0]
                insert = (postpostcol + 1, int(i),)
                c.execute('UPDATE answer SET colans=? WHERE idans=?', insert)
                insert = (self.current_user['id'], interid,)
                c.execute("INSERT INTO author (author,interid) VALUES (?,?)", insert)
            conn.commit()
            conn.close()


def main():
    # parse_command_line()
    port = int(os.environ.get("PORT", 8000))
    app = Application()
    app.listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()

import os; os.chdir(os.path.realpath(__file__).replace('server.py',''))
import flask
import humanize
import logging
import sys
import feedparser
import flask_profiler
import markdown
from quartz import *
import bs4

logger = logging.getLogger('quartz.main')

app = flask.Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = db.config.secret_key
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

#app.config['SERVER_NAME'] = 'quartzlocal.org:8081'

# if cache
if db.config.site.cache:
    db.logger.info('Using GZIP Compression')
    from flask_compress import Compress
    Compress(app)

app.config["flask_profiler"] = {
    "enabled": db.config.developer_mode,
    "storage": {
        "engine": "mongodb"
    },
    "basicAuth":{
        "enabled": True,
        "username": "admin",
        "password": "superSecurePassword"
    },
    'endpointRoot':'admin_profiler',
    "ignore": [
	    "^/static/.*"
	]
}

@app.route('/')
def index():
    items = db.search_items(page_number=1, page_size=20)

    news_feed = feedparser.parse('https://medium.com/feed/quartzboard')
    
    return flask.render_template('home.html', **locals())

@app.route('/api/news')
def get_news():
    """
    Part of the News app on the home page
    This is a test for future plans to use Vue.js inside QB
    """
    news_feed = feedparser.parse('https://medium.com/feed/quartzboard')
    stories = []
    for entry in news_feed.entries:
        soup = bs4.BeautifulSoup(entry.summary, 'lxml')
        story = {}
        story['title'] = entry.title
        story['image'] = soup.find('img')['src']
        story['content'] = soup.find('p').get_text()
        story['href'] = entry.link
        stories.append(story)

    print(stories)

    return flask.jsonify(stories)

@app.route('/test')
def test():
    return flask.render_template('test.html', **locals())

@app.route('/about')
def about():
    return flask.render_template('about.html')

@app.route('/terms')
def terms():
    return flask.render_template('terms.html')

@app.route('/ui_mode')
def switch_mode():
    mode = flask.request.args.get('mode','light')
    print(mode)
    resp = flask.make_response(flask.redirect('/'))
    if mode == 'dark':
        resp.set_cookie('dark_mode', 'on')
    else:
        resp.set_cookie('dark_mode', 'off')
    return resp

@app.route('/confirm', methods = ['GET', 'POST'])
def confirm_age():
    if flask.request.method == 'POST':
        resp = flask.make_response(flask.redirect('/?confirmed=1'))
        resp.set_cookie('confirmed', '1')
        return resp
    else:
        return flask.render_template('confirm.html')

if not db.config.site.show_errors:
    @app.errorhandler(Exception)
    def unhandled_exception(e):
        db.logger.error('Unhandled Exception: %s', (e))
        return flask.render_template('errors/500.html'), 500

@app.before_request
def utility_processor():
    # do the subdomain checker
    user = {}
    is_logged_in = False
    flask.g.is_logged_in = False

    token = flask.request.cookies.get('token')
    if token:
        user = db.get_user(token, search_by='token')
        if not user:
            # user token is invalid
            flask.g.user = {}
            flask.g.is_logged_in = False
            
        else: 
            flask.g.user = user
            if db.config.get('ownerID', '0') == str(user['userID']):
                flask.g.user['role'] = db.get_role('admin')
            else:
                flask.g.user['role'] = db.get_role(user.get('roleID'))

            flask.g.is_logged_in = True
            is_logged_in = True
    else:
        flask.g.user = {}
        
    try:
        rule = flask.request.url_rule.rule
    except:
        # 404?
        return flask.render_template('errors/404.html',error= '404'), 404

    if 'static' in rule or 'api' in rule or 'image' in rule:
        pass
    else:
        if not flask.request.cookies.get('confirmed') and ('confirm' not in flask.request.url_rule.rule):
            pass
    if 'debug' in flask.request.url:
        flask.g.debug_req = True
    else:
        flask.g.debug_req = False

@app.after_request
def apply_caching(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Server"] = "QuartzBoard Version {}".format(db.__version__)
    return response

@app.context_processor
def ctx_processor():
    return {'user': flask.g.user,
            'is_logged_in': flask.g.is_logged_in,
            'dark_mode': flask.request.cookies.get('dark_mode', 'on'),
            'enable_nsfw': flask.request.cookies.get('enable_nsfw', '0'),
            'quartz_config': db.config,
            'is_chrome': flask.request.user_agent.browser == 'chrome'}

template_functions = {'get_popular_tags': db.get_popular_tags,
                        'get_user': db.get_user,
                        'get_tag': db.get_tag,
                        'time_to_human': humanize.naturaltime,
                        'get_images': db.get_images,
                        'db': db,
                        'md': markdown.markdown,
                        'image_utils': image_utils}

app.jinja_env.globals.update(**template_functions)
app.jinja_env.cache = {} # https://blog.socratic.org/the-one-weird-trick-that-cut-our-flask-page-load-time-by-70-87145335f679

flask_profiler.init_app(app)

if __name__ == '__main__':
    """
    If running in single file mode
    this allows the server to run no matter what
    """
    from blueprint.auth import auth_api
    from blueprint.profile import profile_api
    from blueprint.image import image_api
    from blueprint.collection import collection_api
    from blueprint.mass_upload import mass_upload_api
    from blueprint.admin import admin_api

    app.register_blueprint(auth_api)
    app.register_blueprint(profile_api)
    app.register_blueprint(image_api)
    app.register_blueprint(collection_api)
    app.register_blueprint(mass_upload_api)
    app.register_blueprint(admin_api)

    

    app.run('0.0.0.0', db.config.get('port', 8081), threaded=True)

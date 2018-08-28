"""
This is for those who wish to run QuartzBoard with
Gunicorn or any other WSGI applications
"""

from server import app

if __name__ == '__main__':
    print('Running in WSGI mode')
    from blueprint.auth import auth_api
    from blueprint.profile import profile_api
    from blueprint.image import image_api
    from blueprint.admin import admin_api

    app.register_blueprint(auth_api)
    app.register_blueprint(profile_api)
    app.register_blueprint(image_api)
    app.register_blueprint(admin_api)

    flask_profiler.init_app(app)

    app.run('0.0.0.0', db.config.get('port', 8081), threaded=True)
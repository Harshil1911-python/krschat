# -*- coding: utf-8 -*-
import eventlet
eventlet.monkey_patch()

import os
from app import create_app, socketio

app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)

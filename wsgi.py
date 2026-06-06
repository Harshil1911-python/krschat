# -*- coding: utf-8 -*-
"""
KHANDHARS CHAT - Application Entry Point
"""
import os
from app import create_app, socketio

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print("")
    print("  ╔══════════════════════════════════════╗")
    print("  ║       KHANDHARS CHAT Running         ║")
    print("  ╠══════════════════════════════════════╣")
    print("  ║  App:   http://localhost:{}          ║".format(port))
    print("  ║  Admin: http://localhost:{}/admin    ║".format(port))
    print("  ╚══════════════════════════════════════╝")
    print("")
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )

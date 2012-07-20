"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

APP = ['../run.py']
DATA_FILES = [
 '../4store',
 '../COPYING',
 '../data',
 '../html',
 '../libs',
 '../README.md',
 '../requirements.txt',
 'run_app.sh',
 '../rww',
 '../scripts',
 '../setup_env.sh',
 '../tests',
 '../webbox.json.default',
 'webbox.icns',
 '../wsupdate',
 ]

OPTIONS = {
    'iconfile': 'webbox.icns',
    'argv_emulation': True,
    'includes': # all external modules, taken from generate_includes.py
        ['cStringIO', 
        'traceback', 
        'getpass', 
        'twisted.web.server', 
        'webbox', 
        'shutil', 
        'hashlib', 
        'lxml.builder', 
        'lxml', 
        'uuid', 
        'webboxhandler', 
        'websocketclient', 
        'urllib', 
        're', 
        'json', 
        'fourstore', 
        'time', 
        'sqlite3', 
        'twisted.web.wsgi', 
        'httputils', 
        'subscriptions', 
        'journal', 
        'diskstore', 
        'urllib2', 
        'sys', 
        'cElementTree', 
        'webbrowser', 
        'sparqlresults', 
        'twisted.internet.defer', 
        'os.path', 
        'ConfigParser', 
        'httplib', 
        'logging', 
        'twisted.web.static', 
        'twisted.web.util', 
        'sparqlparse', 
        'mimeparse', 
        'pkg_resources', 
        'urlparse', 
        'autobahn.websocket', 
        'setuptools', 
        'twisted.web', 
        'os', 
        'twisted.internet', 
        'OpenSSL', 
        'xml.etree', 
        'lxml._elementpath', 
        'rdflib', 
        'rdflib.plugin', 
        'rdflib.graph', 
        'rdflib.serializer', 
        'rdflib.plugins', 
        'rdflib.plugins.memory', 
        'rdflib.plugins.parsers.rdfxml',
        'rdflib.plugins.parsers.notation3',
        'rdflib.plugins.parsers.nquads',
        'rdflib.plugins.parsers.nt',
        'rdflib.plugins.parsers.ntriples',
        'rdflib.plugins.parsers.trix',
        'rdflib.plugins.serializers.rdfxml',
        'rdflib.plugins.serializers.n3',
        'rdflib.plugins.serializers.nquads',
        'rdflib.plugins.serializers.nt',
        'rdflib.plugins.serializers.turtle',
        'rdflib.plugins.serializers.xmlwriter',
        'rdflib.plugins.serializers.trix',
        'rdfliblocal.jsonld', 
        ]
    }

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

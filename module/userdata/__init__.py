# Userdata module.
# This module should be imported by programs that want to use the userdata system.

# Imports {{{
import sys
import os
import io
import subprocess
import importlib.resources
import gettext
import secrets
import traceback
import fhs
import websocketd
# }}}

''' Documentation. {{{
Use case: single
	Game logs in to userdata and uses storage for single user.
	Implemented as multi-user storage which never connects a user.

Use case: remote-only
On login:
	- User must provide userdata url (there may be a default)
	- Connect to userdata
	- Get login url from userdata
	- Let user log in
	- return handle

Use case: local with optional remote
On boot:
	- Game connects to userdata and logs in
On login:
	- User may provide userdata url if allowed; otherwise there muct be a default
	- If userdata is not the default, connect to it
	- Get login url from userdata
	- Let user log in
	- return handle

Interface:
	- call setup() or run() to start server/game.
	- player callback is called whenever a new player logs in.
	- the object that is passed to it can use database commands; it must not include a user parameter.
}}} '''

# Translations. {{{
def parse_translation(definition): # {{{
	'''Convert a single po file into a dict.
	definition is a str or file.
	Returns the dict.
	'''
	if not isinstance(definition, bytes):
		with open(definition) as f:
			definition = f.read()
	try:
		data = subprocess.run(('msgfmt', '-o', '-', '-'), input = definition, close_fds = True, stdout = subprocess.PIPE).stdout
		assert len(data) > 0
	except:
		print('Warning: translation could not be read', file = sys.stderr)
		traceback.print_exc()
		return None
	terms = gettext.GNUTranslations()
	terms._parse(io.BytesIO(data))
	# Convert catalog to regular dict, just in case it wasn't.
	ret = {k: v for k, v in terms._catalog.items()}
	# Remove info node.
	del ret['']
	return ret
# }}}

def read_translations(path): # {{{
	'''Read all translations at path.
	path must be the name of a directory where *.po files are stored. Each file translates the same strings into a language. The filename is the language code (e.g. nl.po).
	Returns a dict of language code keys with dicts of translations as values.
	'''
	ret = {}
	print('reading translations, path="%s"' % path)
	for po in os.listdir(path):
		filename = os.path.join(path, po)
		lang, ext = os.path.splitext(po)
		if ext != os.extsep + 'po' or lang.startswith('.') or not os.path.isfile(filename):
			continue
		with open(filename, 'rb') as f:
			data = parse_translation(f.read())
		if data is None:
			continue
		ret[lang] = data
		print('read language: %s' % lang)
	return ret
# }}}

def _(template, *args): # {{{
	'''Translate a string into the currenly selected language.
	This function is not used by the module. It is meant to be imported by the game using:
		from userdata import _, N_
	That way, translatable strings can be marked using _('string').'''
	if template in game_strings_python:
		template = game_strings_python[template]
	else:
		print('Warning: translation for "%s" not found in dictionary' % template, file = sys.stderr)
	# Handle template the same as in javascript.
	def replace(match):
		n = int(match.group(1))
		if not 1 <= n <= len(args):
			print('Warning: translation template "%s" references invalid argument %d' % (template, n), file = sys.stderr)
			return b'[%d]' % n
		return args[n - 1]
	return re.sub(rb'\$(\d)', template, replace)
# }}}

def N_(template): # {{{
	'This function is used to mark translatable strings that should not be translated where they are defined.'
	return template
# }}}
# }}}

class Access: # {{{
	def __init__(self, obj, channel): # {{{
		self.obj = obj
		self.channel = channel
	# }}}
	def __getattr__(self, attr): # {{{
		func = getattr(self.obj, attr)
		if not callable(func):
			raise AttributeError('invalid function')
		def ret(*a, **ka): # {{{
			if 'wake' in ka:
				wake = ka.pop('wake')
				func.bg(lambda ret: wake(ret), self.channel, *a, **ka)
				return (yield)
			return func.event(self.channel, *a, **ka)
		# }}}
		return ret
# }}}
# }}}

class Player: # {{{
	'An instance of this class is a connection to a (potential) player.'
	_pending_gcid = {}
	_active_gcid = {}
	def __init__(self, remote, settings): # {{{
		self._player = None	# Do this first, to allow __getattr__ to check it.
		self._remote = remote
		self._settings = settings
		remote._websocket_closed = self._closed
		# A gcid in the query string is used by an external userdata to connect a player.
		if 'channel' not in remote.data['query']:
			# No gcid, so this connection is for a player to log in to this game.
			# Make it a call, because it needs to yield from.
			websocketd.call(None, self._finish_init)
			return

		# A connection with a gcid should be a userdata providing access to this game for a player.

		# This is not a player, so don't give it an id, but do define the members.
		self._channel = None
		self._name = None
		self._gcid = None
		self._dcid = None

		# Set player from gcid.
		gcids = remote.data['query']['gcid']
		if len(gcids) != 1:
			print('invalid gcids in query string')
			raise ValueError('invalid gcids')
		gcid = gcids[0]
		channel = int(remote.data['query']['channel'][0])
		name = remote.data['query']['name'][0]

		# setup_connect handles connecting the userdata to the game.
		# This can also be called by the userdata on an existing connection.
		websocketd.call(None, self.setup_connect, channel, name, None, gcid)
	# }}}

	def _finish_init(self, logged_out = False): # {{{
		'Second stage of constructor. This is a separate function so it can yield.'
		wake = (yield)
		self._userdata = None
		self._name = None
		self._local = Access(self._settings['server']._local_userdata, 0)
		self._channel = False
		self._gcid = secrets.token_urlsafe()
		while self._gcid in self._pending_gcid or self._gcid in self._active_gcid:
			self._gcid = secrets.token_urlsafe()
		self._pending_gcid[self._gcid] = self
		if self._settings['allow-other']:
			gcid = self._gcid
		else:
			gcid = None
		if self._settings['allow-local']:
			self._dcid = (yield from self._local.create_dcid(self._gcid, wake = wake))
		else:
			self._dcid = None
		sent_settings = {'allow-local': self._settings['allow-local'], 'allow-other': self._settings['allow-other'], 'local-userdata': self._settings['local-userdata']}
		if logged_out:
			sent_settings['logout'] = '1';
		self._remote.userdata_setup.event(self._settings['default'], self._settings['game-url'], sent_settings, gcid, self._dcid)
	# }}}

	def _revoke_links(self): # {{{
		#print('revoking links', repr(self._pending_gcid), repr(self._active_gcid), repr(self._name), repr(self._gcid), repr(self._dcid), file = sys.stderr)
		if self._gcid is not None:
			if self._name is None:
				self._pending_gcid.pop(self._gcid)
			else:
				self._active_gcid.pop(self._gcid)
			self._gcid = None
		if self._dcid is not None:
			if self._name is None:
				self._local.drop_pending_dcid(self._dcid)
			else:
				self._local.drop_active_dcid(self._dcid)
			self._dcid = None
	# }}}
	def _closed(self): # {{{
		wake = (yield)
		self._revoke_links()
		if self._channel is not None:
			# This is a player connection.
			if self._gcid in self._settings['server'].players:
				self._settings['server'].players.pop(self._gcid)
				self._settings['server']._players.pop(self._gcid)
			# Notify userdata that user is lost.
			if self._userdata is not None:
				yield from self._userdata.disconnected(wake = wake)
		else:
			# This is a userdata connection.
			# TODO: Kick users of this data.
			pass
		if hasattr(self._player, '_closed'):
			c = self._player._closed()
			if type(c) is type((lambda: (yield))()):
				c.send(None)
				try:
					c.send(wake)
				except StopIteration:
					return
				yield from c
	# }}}

	def setup_connect(self, channel, name, language, gcid): # {{{
		'''Set up new external player on this userdata connection.
		This call is made by a userdata, either at the end of the
		contructor of the connection object, or on a connection that is
		already used for another player.'''
		wake = (yield)

		# Check that this is not a player connection.
		assert self._channel is None

		# Check that the gcid is valid.
		if gcid not in self._pending_gcid:
			print('invalid gcid in query string')
			raise ValueError('invalid gcid')

		# Set up the player.
		player = self._pending_gcid.pop(gcid)
		self._active_gcid[gcid] = player
		player._name = name
		player._managed_name = None
		player._language = language

		# Check and set player id.
		assert player._channel is False
		player._channel = self._settings['server']._next_channel
		self._settings['server']._next_channel += 1

		# Set self._player so calls to the userdata server are allowed.
		assert self._player in (None, True)
		self._player = True

		# Set the userdata.
		player._userdata = Access(self._remote, channel)
		yield from player._setup_player(wake)
	# }}}

	def _setup_player(self, wake): # {{{
		'Handle player setup. This is called both for managed and external players.'
		# Initialize db
		assert self._player is None
		player_config = self._settings['server']._player_config
		if player_config is not None:
			yield from self._userdata.setup_db(player_config, wake = wake)

		# Record internal player object in server.
		self._settings['server']._players[self._channel] = self

		# Create user player object and record it in the server.
		try:
			self._player = self._settings['player'](self._gcid, self._name, self._userdata, self._remote, self._managed_name)
		except:
			# Error: close connection.
			self._remote._websocket_close()
			return
		self._settings['server'].players[self._channel] = self._player

		self._remote.userdata_translate.event(system_strings[self._language] if self._language in system_strings else None, game_strings_html[self._language] if self._language in game_strings_html else None)
		self._remote.userdata_setup.event(None, None, {'name': self._name, 'managed': self._managed_name})

		try:
			player_init = self._player._init(wake)
			# If _init is a generator, wait for it to finish.
			if type(player_init) is type((lambda: (yield))()):
				yield from player_init
		except:
			# Error: close connection.
			self._remote._websocket_close()
	# }}}

	def userdata_logout(self): # {{{
		wake = (yield)
		print('logout')
		self._player = None	# FIXME: close link with userdata as well.
		# Emulate call() implementation.
		generator = self._finish_init(logged_out = True)
		generator.send(None)
		try:
			generator.send(wake)
		except StopIteration:
			return
		yield from generator
	# }}}

	def __getattr__(self, attr): # {{{
		if self._player in (None, True):
			raise AttributeError('invalid attribute for anonymous user')
		return getattr(self._player, attr)
	# }}}
# }}}

class Game_Connection: # {{{
	'''This is a connection object that is used for the connection to the local userdata.
	This is the connection that calls login_game() on the userdata.'''
	def __init__(self, remote, settings): # {{{
		self.remote = remote
		self.settings = settings
	# }}}
	def setup_connect_player(self, channel, gcid, name, fullname, language): # {{{
		'''Report successful login of a managed player.'''
		wake = (yield)
		# XXX What if the player was already logged in?
		assert gcid in Player._pending_gcid
		player = Player._pending_gcid.pop(gcid)
		Player._active_gcid[gcid] = player
		player._managed_name = name
		player._name = fullname
		player._language = language

		assert player._channel is False
		player._channel = self.settings['server']._next_channel
		self.settings['server']._next_channel += 1
		self.settings['userdata'].access_managed_player.bg(wake, channel, player._channel, player._name)
		yield
		player._userdata = Access(self.settings['userdata'], player._channel)

		yield from player._setup_player(wake)
# }}}
# }}}

def setup(player, config, db_config, player_config, httpdirs = ('html',), *a, **ka): # {{{
	'''Set up a game with userdata.
	@param port: The port to listen for game clients on.
	@param game: a dict with information about the game, sent to userdata when connecting.
	@param player: called when a player has authenticated with a userdata server. This should be a function or class just like websocketd.RPC uses.
	@param userdata: a port for the userdata to connect to (this may be an url, or any format that python-network understands).
	@param httpdirs: sequence of directory names (searched for as data files using python-fhs) where the web interface is.
	'''
	assert config['default-userdata'] != '' or config['allow-local']	# If default is '', allow-local must be True.

	game_settings = {}	# This is filled in after construction, but before use.
	local = websocketd.RPC(config['userdata-websocket'], (lambda remote: Game_Connection(remote, game_settings)) if config['allow-local'] else None)
	local._websocket_closed = lambda: sys.exit(1)
	if not local.login_game(0, config['userdata-login'], config['userdata-game'], config['userdata-password'], config['allow-new-players']):
		raise PermissionError('Game login failed')
	if db_config is not None:
		local.setup_db(0, db_config)

	settings = {
		'game-url': config['game-url'],
		'player': player,
		'default': config['default-userdata'],
		'allow-other': not config['no-allow-other'],
		'allow-local': config['allow-local'],
		'local-userdata': config['userdata-url'],
		'allow-new-players': config['allow-new-players'],
	}
	ret = websocketd.RPChttpd(config['port'], lambda remote: Player(remote, settings), *a, httpdirs = httpdirs, **ka)
	settings['server'] = ret

	# Give access to selected variables from local userdata callbacks.
	game_settings['server'] = ret
	game_settings['userdata'] = local
	game_settings['player'] = player

	# Store player config for use when a new player connects.
	ret._player_config = player_config

	# All logged in players (for internal use). Key is player id, value is Player object.
	ret._players = {}

	# All logged in players (for calling program). Key is player id, value is caller's player object.
	ret.players = {}

	# Store local userdata for later use.
	ret._local_userdata = local

	# Keep track of player IDs.
	ret._next_channel = 1

	return ret, Access(local, 0)
# }}}

def run(*a, **ka): # {{{
	'''Set up a server and run the main loop.
	This function does not allow tweaks to the server. If those are needed, use setup() and start the main loop manually.
	All arguments are passed unchanged to setup().'''
	server = setup(*a, **ka)
	websocketd.fgloop()
# }}}

def fhs_init(url, name, *a, **ka): # {{{
	'''Add default fhs options and run fhs.init to parse the commandline.'''
	if 'game_name' in ka:
		game_name = ka.pop('game_name')
	else:
		game_name = name
	# Set default options.
	fhs.option('userdata', 'name of file containing userdata url, login name, game name and password', default = 'userdata.ini')
	fhs.option('game-url', 'game url', default = '')
	fhs.option('default-userdata', 'default servers for users to connect to (empty string for locally managed)', default = '')
	fhs.option('allow-local', 'allow locally managed users', argtype = bool)
	fhs.option('no-allow-other', 'do not allow a non-default userdata server', argtype = bool)
	fhs.option('allow-new-players', 'allow registering new locally managed users', argtype = bool)

	# Parse commandline.
	config = fhs.init(*a, **ka)

	# Read translations. {{{
	global system_strings, game_strings_html, game_strings_python
	# System translations.
	langfiles = importlib.resources.files(__package__).joinpath('lang')
	print('lang', langfiles)
	system_strings = {}
	pofiles = []
	for lang in langfiles.iterdir():
		if not lang.name.endswith(os.extsep + 'po'):
			continue
		print('parsing stings for "%s"' % lang)
		system_strings[os.path.splitext(os.path.basename(lang))[0]] = parse_translation(lang.read_bytes())

	# Game translations.
	dirs = fhs.read_data('lang', dir = True, multiple = True, opened = False)
	game_strings_html = {}
	game_strings_python = {}
	for d in dirs:
		s = read_translations(os.path.join(d, 'html'))
		game_strings_html.update(s)
		s = read_translations(os.path.join(d, 'python'))
		game_strings_python.update(s)
	# }}}

	# Add userdata info from file.
	with open(config['userdata']) as f:
		for kv in f:
			kv = kv.strip()
			if kv == '' or kv.startswith('#'):
				continue
			k, v = map(str.strip, kv.split('=', 1))
			if k not in ('url', 'websocket', 'login', 'game', 'password'):
				print('Ignoring unknown key "%s" from config file %s' % (k, config['userdata']))
				continue
			config['userdata-' + k] = v

	# Return result.
	return config
# }}}

# vim: set foldmethod=marker :

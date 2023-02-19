# Userdata module.
# This module should be imported by programs that want to use the userdata system.

# Imports {{{
import sys
import secrets
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

class Access: # {{{
	def __init__(self, obj, user_id): # {{{
		self.obj = obj
		self.user_id = user_id
	# }}}
	def __getattr__(self, attr): # {{{
		func = getattr(self.obj, attr)
		if not callable(func):
			raise AttributeError('invalid function')
		def ret(*a, **ka): # {{{
			if 'wake' in ka:
				wake = ka.pop('wake')
				func.bg(lambda ret: wake(ret), self.user_id, *a, **ka)
				return (yield)
			return func.event(self.user_id, *a, **ka)
		# }}}
		return ret
# }}}
# }}}

class Player: # {{{
	'An instance of this class is a connection to a (potential) player.'
	_pending = {}
	def __init__(self, remote, settings): # {{{
		self._player = None	# Do this first, to allow __getattr__ to check it.
		self._remote = remote
		self._settings = settings
		remote._websocket_closed = self._closed
		if 'token' not in remote.data['query']:
			# No token, so this connection is for a player to log in to this game.
			# Make it a call, because it needs to yield from.
			websocketd.call(None, self._finish_init)
			return

		# A connection with a token should be a userdata providing access to this game for a player.

		# This is not a player, so don't give it an id, but do define the members.
		self._id = None
		self._token = None

		# Set player from token.
		tokens = remote.data['query']['token']
		if len(tokens) != 1:
			print('invalid tokens in query string')
			raise ValueError('invalid tokens')
		token = tokens[0]
		uid = int(remote.data['query']['uid'][0])
		name = remote.data['query']['name'][0]

		websocketd.call(None, self.setup_connect, uid, name, token)
	# }}}

	def _finish_init(self, logged_out = False): # {{{
		'Second stage of constructor. This is a separate function so it can yield.'
		wake = (yield)
		self._userdata = None
		self._name = None
		self._local = Access(self._settings['server']._local_userdata, 0)
		self._id = False
		self._token = secrets.token_urlsafe()
		while self._token in self._pending:
			self._token = secrets.token_urlsafe()
		self._pending[self._token] = self
		if self._settings['allow-other']:
			token = self._token
		else:
			token = None
		if self._settings['allow-local']:
			self._utoken = (yield from self._local.create_token(self._token, wake = wake))
		else:
			self._utoken = None
		sent_settings = {'allow-local': self._settings['allow-local'], 'allow-other': self._settings['allow-other'], 'local-userdata': self._settings['local-userdata']}
		if logged_out:
			sent_settings['logout'] = '1';
		self._remote.userdata_setup.event(self._settings['default'], self._settings['game-url'], sent_settings, token, self._utoken)
	# }}}

	def _revoke_links(self): # {{{
		self._pending.pop(self._token)
		self_token = None
		if self._utoken is not None:
			self._local.drop_token(self._utoken)
			self._utoken = None
	# }}}
	def _closed(self): # {{{
		wake = (yield)
		self._revoke_links()
		if self._id is not None:
			# This is a player connection.
			if self._id in self._settings['server'].players:
				self._settings['server'].players.pop(self._id)
				self._settings['server']._players.pop(self._id)
			# Notify userdata that user is lost.
			if self._userdata is not None:
				yield from self._userdata.disconnected(wake = wake)
		else:
			# This is a userdata connection.
			# TODO: Kick users of this data.
			pass
		if hasattr(self._player, 'closed'):
			c = self._player.closed()
			if type(c) is type((lambda: (yield))()):
				c.send()
				c.send(wake)
				yield from c
	# }}}

	def setup_connect(self, uid, name, token): # {{{
		'Set up new player on this userdata connection.'
		wake = (yield)
		assert self._id is None
		if token not in self._pending:
			print('invalid token in query string')
			raise ValueError('invalid token')
		player = self._pending.pop(token)
		player._token = None
		player._name = name
		player._managed_name = None
		assert player._id is False
		player._id = self._settings['server']._nextid
		self._settings['server']._nextid += 1

		# Set self._player so calls to the userdata server are allowed.
		assert self._player in (None, True)
		self._player = True

		# Set the userdata.
		player._userdata = Access(self._remote, uid)
		yield from player._setup_player(wake)
	# }}}

	def _setup_player(self, wake): # {{{
		# Initialize db
		assert self._player is None
		player_config = self._settings['server']._player_config
		if player_config is not None:
			yield from self._userdata.setup_db(player_config, wake = wake)

		# Record internal player object in server.
		self._settings['server']._players[self._id] = self

		# Create user player object and record it in the server.
		self._player = self._settings['player'](self._id, self._name, self._userdata, self._remote, self._managed_name)
		self._settings['server'].players[self._id] = self._player
		player_init = self._player._init(wake)
		# If _init is a generator, wait for it to finish.
		if type(player_init) is type((lambda: (yield))()):
			yield from player_init

		self._remote.userdata_setup.event(None, None)
	# }}}

	def userdata_logout(self): # {{{
		wake = (yield)
		print('logout')
		self._player = None	# FIXME: close link with userdata as well.
		# Emulate call() implementation.
		generator = self._finish_init(logged_out = True)
		generator.send(None)
		generator.send(wake)
		yield from generator
	# }}}

	def __getattr__(self, attr): # {{{
		if self._player is None:
			raise AttributeError('invalid attribute for anonymous user')
		return getattr(self._player, attr)
	# }}}
# }}}

class Game_Connection: # {{{
	def __init__(self, remote, settings): # {{{
		self.remote = remote
		self.settings = settings
	# }}}
	def setup_connect_player(self, userid, token, name, fullname): # {{{
		'Report successful login of a managed player.'
		wake = (yield)
		# XXX What if the player was already logged in?
		assert token in Player._pending
		player = Player._pending.pop(token)
		player._managed_name = name
		player._name = fullname

		assert player._id is False
		player._id = self.settings['server']._nextid
		self.settings['server']._nextid += 1
		self.settings['userdata'].access_managed_player.bg(wake, userid, player._id, player._name)
		yield
		player._userdata = Access(self.settings['userdata'], player._id)

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
	local = websocketd.RPC(config['userdata'], (lambda remote: Game_Connection(remote, game_settings)) if config['allow-local'] else None)
	local._websocket_closed = lambda: sys.exit(1)
	if not local.login_game(0, config['username'], config['gamename'], config['password']):
		raise PermissionError('Game login failed')
	if db_config is not None:
		local.setup_db(0, db_config)

	settings = {
		'game-url': config['game-url'],
		'player': player,
		'default': config['default-userdata'],
		'allow-other': not config['no-allow-other'],
		'allow-local': config['allow-local'],
		'local-userdata': config['userdata'],
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
	ret._nextid = 1

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
	if 'gamename' in ka:
		gamename = ka.pop('gamename')
	else:
		gamename = name
	# Set default options.
	fhs.option('userdata', 'userdata server', default = url)
	fhs.option('username', 'userdata login name', default = name)
	fhs.option('gamename', 'userdata game name', default = gamename)
	fhs.option('password', 'userdata password', default = '')
	fhs.option('game-url', 'userdata game url', default = '')
	fhs.option('default-userdata', 'default servers for users to connect to (empty string for locally managed)', default = '')
	fhs.option('allow-local', 'allow locally managed users', argtype = bool)
	fhs.option('no-allow-other', 'do not allow a non-default userdata server', argtype = bool)

	# Parse commandline.
	config = fhs.init(*a, **ka)

	# Return result.
	return config
# }}}

# vim: set foldmethod=marker :

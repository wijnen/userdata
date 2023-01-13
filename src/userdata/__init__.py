# Userdata module.
# This module should be imported by programs that want to use the userdata system.

import websocketd
import secrets
import fhs

'''
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
'''

class Access: # {{{
	def __init__(self, obj, user_id, player = ''):
		self.obj = obj
		self.user_id = user_id
		self.player = player
	def __getattr__(self, attr):
		func = getattr(self.obj, attr)
		if not callable(func):
			raise AttributeError('invalid function')
		def ret(*a, **ka):
			if 'cb' in ka:
				cb = ka.pop('cb')
				return func.bg(cb, self.user_id, *a, player = self.player, **ka)
			else:
				return func.event(self.user_id, *a, player = self.player, **ka)
		return ret
# }}}

class Player:
	'An instance of this class is a connection to a (potential) player.'
	_pending = {}
	def __init__(self, remote, settings):
		self._player = None	# Do this first, to allow __getattr__ to check it.
		self._remote = remote
		self._settings = settings
		remote.closed = self._closed
		if 'token' in remote.data['query']:
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
			self.setup_connect(0, token)

			return

		# No token, so this connection is for a player to log in to this game.
		self._userdata = None
		self._name = None
		self._local = Access(settings['server']._userdata_servers[''][0], 0)
		self._id = self._settings['server']._userdata_servers[''][1]
		self._settings['server']._userdata_servers[''][1] += 1
		self._token = secrets.token_urlsafe()
		while self._token in self._pending:
			self._token = secrets.token_urlsafe()
		self._pending[self._token] = self
		self._remote.userdata_setup.event(self._settings['default'], self._settings['game-url'], self._settings['containers'], {}, self._token)
	def _revoke_links(self):
		if self._token is not None:
			self._pending.pop(self._token)
	def _closed(self):
		self._revoke_links()
		if self._id is not None:
			# This is a player connection.
			if self._id in self._settings['server'].players:
				self._settings['server'].players.pop(self._id)
				self._settings['server']._players.pop(self._id)
			# Notify userdata that user is lost.
			if self._userdata is not None:
				self._userdata.disconnected()
		else:
			# This is a userdata connection.
			# TODO: Kick users of this data.
			pass
	def setup_connect(self, uid, token):
		'Set up new player on this userdata connection.'
		assert self._id is None
		if token not in self._pending:
			print('invalid token in query string')
			raise ValueError('invalid token')
		player = self._pending.pop(token)
		player._token = None

		# Set self._player so calls to the userdata server are allowed.
		assert self._player in (None, True)
		self._player = True

		# Initialize db
		assert player._player is None
		player._userdata = Access(self._remote, uid)
		player_config = player._settings['server']._player_config
		if player_config is not None:
			player._userdata.setup_db(player_config)

		# Record internal player object in server.
		player._settings['server']._players[player._id] = player

		# Create user player object and record it in the server.
		player._player = player._settings['player'](player._id, player._userdata)
		player._settings['server'].players[player._id] = player._player

		player._remote.userdata_setup.event(None)

	def setup_login_player(self):
		'Confirm that a player has logged in'
		assert settings['allow_local']
		# XXX What if the player was already logged in?
		def cb(name):
			self._name = name
			self._player = self._settings['player'](self._remote, self._name, self._local)
			self._link = None
		self._local.verify_player_login(player = self._id, ret = cb)
	def __getattr__(self, attr):
		if self._player is None:
			raise AttributeError('invalid attribute for anonymous user')
		return getattr(self._player, attr)

def setup(player, config, db_config, player_config, default = None, allow_other = True, allow_local = True, httpdirs = ('html',)):
	'''Set up a game with userdata.
	@param port: The port to listen for game clients on.
	@param game: a dict with information about the game, sent to userdata when connecting.
	@param player: called when a player has authenticated with a userdata server. This should be a function or class just like websocketd.RPC uses.
	@param userdata: a port for the userdata to connect to (this may be an url, or any format that python-network understands).
	@param default: the default userdata for users. allow_other must be True if this is None. If this is set to an empty string, the default is to use the game's userdata and allow_local must be True.
	@param allow_other: if True, users may connect to a non-default userdata.
	@param allow_local: if True, users may connect to the game's userdata.
	@param httpdirs: sequence of directory names (searched for as data files using python-fhs) where the web interface is.
	'''
	assert default is not None or allow_other is True	# If default is None, allow_other must be True.
	assert 'userdata' in config				# There must be a local userdata to present a login screen.
	assert default != '' or allow_local is True		# If default is '', allow_local must be True.

	assert 'userdata' in config
	local = websocketd.RPC(config['userdata'])
	if not local.login_game(0, config['username'], config['password'], config['containers'][0]):
		raise PermissionError('Game login failed')
	if db_config is not None:
		local.setup_db(0, db_config, player = '')

	ret = websocketd.RPChttpd(config['port'], lambda remote: Player(remote, {'server': ret, 'containers': config['containers'], 'game-url': config['game-url'], 'player': player, 'default': default, 'allow_other': allow_other, 'allow_local': allow_local}), httpdirs = httpdirs)

	# Store player config for use when a new player connects.
	ret._player_config = player_config

	# All logged in players (for internal use). Key is player id, value is Player object.
	ret._players = {}

	# All logged in players (for calling program). Key is player id, value is caller's player object.
	ret.players = {}

	# Keep track of all userdata servers that are connected.
	ret._userdata_servers = {}
	# Insert local server in dict.
	ret._userdata_servers[''] = [local, 1]

	return ret

def run(*a, **ka):
	'''Set up a server and run the main loop.
	This function does not allow tweaks to the server. If those are needed, use setup() and start the main loop manually.
	All arguments are passed unchanged to setup().'''
	server = setup(*a, **ka)
	websocketd.fgloop()

def fhs_init(url, name, *a, **ka):
	'''Add default fhs options and run fhs.init to parse the commandline.'''
	# Set default options.
	fhs.option('userdata', 'userdata server', default = url)
	fhs.option('username', 'userdata login name', default = name)
	fhs.option('password', 'userdata password', default = '')
	fhs.option('containers', 'userdata containers', multiple = True)
	fhs.option('game-url', 'userdata game url', default = '')

	# Prepare default for containers.
	if 'default_containers' in ka:
		default_containers = ka.pop('default_containers')
	else:
		default_containers = [name]

	# Parse commandline.
	config = fhs.init(*a, **ka)

	# Apply default for containers.
	if len(config['containers']) == 0:
		config['containers'] = default_containers

	# Return result.
	return config

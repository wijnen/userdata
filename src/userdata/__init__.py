# Userdata module.
# This module should be imported by programs that want to use the userdata system.

import websocketd

'''
Use case: single
	Game logs in to userdata and uses storage for single user.
	Implemented as multi-user storage which never connects a user.

Use case: remote-only
On legin:
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
	def __init__(self, obj, user_id, player = None):
		self.obj = obj
		self.user_id = user_id
		self.player = player
	def __getattr__(self, attr):
		func = getattr(self.obj, attr)
		if not callable(func):
			raise AttributeError('invalid function')
		return lambda *a, player = '', **ka: func(self.user_id, *a, player = self.player if player == '' else player, **ka)
# }}}

class Player:
	'An instance of this class is a connection to a (potential) player.'
	def __init__(self, remote, settings):
		remote.closed = self._closed
		self._remote = remote
		self._settings = settings
		self._userdata = None
		self._player = None
		self._name = None
		self._id = {}
		if settings['server']._userdata[''] is None:
			self._local = None
		else:
			self._local = Access(settings['server']._userdata[''][0], 0)
		self._remote.setup.event({k: v for k, v in settings.items() if k in ('default', 'allow_local', 'allow_other')})
	def setup_request_login_link(self):
		'Attempt to log in as a local (server-owned) player'
		assert settings['allow_local']
		if self._link is not None:
			return self._link
		self._id = self._settings['server']._userdata[''][1]
		self._settings['server']._userdata[''][1] += 1
		return self._local.request_login_link(player = self._id)
	def _revoke_links(self):
		for player in self._id:
			self._local.revoke_login_link(player = player)
		self._id = {}
	def _closed(self):
		self._revoke_links()
	def setup_login_player(self):
		'Confirm that a player has logged in'
		assert settings['allow_local']
		self._name = self._local.verify_player_login(player = self._id)
		# XXX What if the player was already logged in?
		self._player = self._settings['player'](self._remote, self._name, self._local)
		self._link = None
	'''
	def _obsolete(self):
		if settings['allow_other'] is False:
			# Use the default without asking the user.
			if settings['default'] in settings['server']._userdata_servers:
				# Use existing userdata connection.
				self._userdata = settings['server']._userdata_servers[settings['default']]
			else:
				# Use new remote userdata connection.
				self._userdata = websocketd.RPC(settings['default'])
				self._userdata.login_game(None, None, self._settings['game'])
				settings['server']._userdata_servers[settings['default']] = self._userdata
			# Wait for player (with id 0) to log in.
			self._id = 0
			self._userdata.request_login_url.bg(self._receive_login, settings['game'], self._id)
		elif settings['default'] is None:
			# Request url from player.
			remote.get_userdata.bg(self._get_userdata)
		else:
			# Use default, but allow the user to change it.
			if settings['default'] in settings['server']._userdata_servers:
				# Use existing userdata connection.
				self._userdata = settings['local']
			else:
				# Use new remote userdata connection.
				self._userdata = websocketd.RPC(settings['default'])
				self._userdata.login_game(None, None, self._settings['game'])
				settings['server']._userdata_servers[settings['default']] = self._userdata
			self._userdata.request_login_url.bg(self._receive_login, settings['game'])
	def _receive_login(self, url):
		'Login url which was requested from userdata server has been received; forward it to player.'
		self._remote.login.bg(self._done_login, url, self._settings['allow_other'])
		self._waiting = self._userdata.wait_for_login.bg(self._logged_in, self._id)
	def _logged_in(self, name):
		'The player has logged in.'
		if name is None:
			# Login failed; user provided new userdata url.
			pass # XXX
		self._name = name
		self._player = self._settings['player'](self._remote, self._name, self._userdata)
	def _get_userdata(self, userdata_server):
		'There was no default and user has provided a userdata server.'
		self._userdata = websocketd.RPC(userdata_server)
		self._userdata.login_game(None, None, self._settings['game'])
		self._userdata.request_login_url.bg(lambda url: remote.login.event(url))
		self._userdata.wait_for_login.bg(self._logged_in)
	'''
	def __getattr__(self, attr):
		if self._player is None:
			raise AttributeError('invalid attribute for anonymous user')
		return getattr(self._player, attr)

def setup(player, config, default = None, allow_other = True, allow_local = True, httpdirs = ('html',)):
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
	assert allow_local is False or 'userdata' in config	# If local connections are allowed, there must be a local userdata.
	assert default != '' or allow_local is True		# If default is '', allow_local must be True.

	if 'userdata' in config:
		local = websocketd.RPC(config['userdata'])
		err = local.login_game(0, config['username'], config['password'], config['game'])
		if err is not None:
			raise PermissionError(err)
	else:
		local = None

	ret = websocketd.RPChttpd(config['port'], lambda remote: Player(remote, {'server': ret, 'game': game, 'player': player, 'default': default, 'allow_other': allow_other, 'allow_local': allow_local}), httpdirs = httpdirs)
	ret._userdata_servers = {}
	if local is not None:
		ret._userdata_servers[''] = (local, 1)
	return ret

def run(*a, **ka):
	'''Set up a server and run the main loop.
	This function does not allow tweaks to the server. If those are needed, use setup() and start the main loop manually.
	All arguments are passed unchanged to setup().'''
	server = setup(*a, **ka)
	websocketd.fgloop()

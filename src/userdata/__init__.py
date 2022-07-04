# Userdata module.
# This module should be imported by programs that want to use the userdata system.

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

class Player:
	def __init__(self, remote, settings):
		self._remote = remote
		self._settings = settings
		self._userdata = None
		self._player = None
		self._name = None
		if settings['allow_other'] is False:
			# Use the default without asking the user.
			if settings['default'] == '':
				# Use local userdata.
				self._userdata = settings['local']
			else:
				# Use remote userdata.
				self._userdata = websocketd.RPC(settings['default'])
			url = udata.request_login_url.bg(lambda url: remote.login.event(url), settings['game'])
			udata.wait_for_login.bg(self._logged_in)
		elif settings['default'] is None:
			# Request url from player.
			remote.get_userdata.bg(self._get_userdata)
		else:
			# Use default, but allow the user to change it.
			if settings['default'] == '':
				# Use local userdata.
				udata = settings['local']
			else:
				# Use remote userdata.
				udata = websocketd.RPC(settings['default'])
			udata.request_login_url.bg(self._receive_login, settings['game'])
	def _receive_login(self, url):
		'Login url which was requested from userdata server has been received; forward it to player.'
		self._remote.login.bg(url)
		self._userdata.wait_for_login.bg(self._logged_in)
	def _logged_in(self, name):
		'Other userdata servers were not allowed and user has logged in.'
		self._set_player(name, None) # FIXME
	def _get_userdata(self, userdata_server):
		'There was no default and user has provided a userdata server.'
		pass # TODO
	def _set_player(self, name, userdata):
		self._name = name
		self._userdata = userdata
		self._player = self._settings['player'](self._remote, self._name, userdata)
	def __getattr__(self, attr):
		if self._player is None or 'login' in attr:
			raise AttributeError('invalid attribute for anonymous user')
		return getattr(self._player, attr)

def setup(port, game, player, userdata = None, default = None, allow_other = True, allow_local = True, httpdirs = ('html',)):
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
	assert allow_local is False or userdata is not None	# If local connections are allowed, there must be a local userdata.
	assert default is not '' or allow_local is True		# If default is '', allow_local must be True.

	if userdata is not None:
		local = websocketd.RPC(userdata['port'])
		err = local.login(userdata['user'], userdata['password'])
		if err is not None:
			raise PermissionError(err)
	else:
		local = None

	return RPChttpd(port, lambda remote: Player(remote, {'game': game, 'player': player, 'local': local, 'default': default, 'allow_other': allow_other, 'allow_local': allow_local}), httpdirs = httpdirs)

def run(*a, **ka):
	'''Set up a server and run the main loop.
	This function does not allow tweaks to the server. If those are needed, use set() and start the main loop manually.
	All arguments are passed unchanged to setup().'''
	server = setup(*a, **ka)
	websocketd.fgloop()

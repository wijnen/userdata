# vim: set foldmethod=marker :

# Imports {{{
import sys
import os
import re
import pymysql
import crypt
import getpass
# }}}

'''Database setup: {{{
# Install dependencies.
sudo apt install mariadb-server python3-pymysql

# Enter settings.
export host=localhost
export user=db_user
export password=db_password
export database=db_database # probably the same as db_user

# Write settings to file so the server can use them.
cat > db.ini <<EOF
host = $host
user = $user
password = $password
database = $database
EOF

# Add user and database to MySQL.
sudo mysql <<EOF
CREATE DATABASE $database;
CREATE USER '$user'@'$host' IDENTIFIED BY '$password';
GRANT ALL PRIVILEGES ON $database.* TO '$user'@'$host';
FLUSH PRIVILEGES;
EOF
}}}'''

# Global variables. {{{
debug_db = 'DBDEBUG' in os.environ
# The config file is in windows ini format (lines with key = value). # for comments. Empty lines allowed.
# Keys are host, user, password, database. All are required. No others are allowed.
config = os.environ.get('DBCONFIG', 'db.ini')

# These files can be used using the setup functions. This is optional.
userdefs = os.environ.get('DBUSER', 'db-user.ini')
tabledefs = os.environ.get('DBTABLES', 'db-tables.ini')

db = None
cursor = None
database = None

global_prefix = os.environ.get('DBPREFIX')
have_global_prefix = global_prefix is not None
if global_prefix is None:
	global_prefix = ''
# }}}

def connect(reconnect = False): # {{{
	'''If the connection is active, nothing happens, unless reconnect is True.'''
	global db, cursor, database
	if db is not None and cursor is not None:
		# Already connected.
		if reconnect:
			db.close()
		else:
			# ignore request.
			return
	cfg = {key.strip(): value.strip() for key, value in (x.split('=', 1) for x in open(config).read().split('\n') if '=' in x and not x.strip().startswith('#'))}
	host = cfg.pop('host')
	user = cfg.pop('user')
	password = cfg.pop('password')
	database = cfg.pop('database')
	assert len(cfg) == 0
	db = pymysql.connect(host = host, user = user, password = password, database = database)
	cursor = db.cursor()
# }}}

def assert_is_id(name): # {{{
	'Check that a name is a valid id (mostly to protect against injections)'
	assert isinstance(name, str)
	assert re.match('^[a-zA-Z_$][a-zA-Z_0-9$]*$', name)
# }}}

def mangle_name(name):  # {{{
	'Return name with special characters replaced such that it is a valid id.'
	ret = ''
	for x in name:
		if 'a' <= x <= 'z' or 'A' <= x <= 'Z' or '0' <= x <= '9':
			ret += x
		elif x == '_':
			ret += '$'
		else:
			ret += '$%02x$' % ord(x)
	# Sanity check.
	if len(ret) > 0:
		assert_is_id(ret)
	return ret
# }}}

def _tabsplit(containers): # {{{
	if containers == '':
		return []
	return containers.split('\t')
# }}}

def mktable(user_id, container, player, table): # {{{
	'Create SQL table name'
	return global_prefix + user_id + '_' + container + '_' + player + '_' + table
# }}}

# Main accesssing functions. {{{
def write(cmd, *args): # {{{
	if debug_db:
		print('db writing: %s%s)' % (cmd, repr(args)), file = sys.stderr)
	cursor.execute(cmd, args)
	db.commit()
# }}}

def read(cmd, *args): # {{{
	if debug_db:
		print('db reading: %s%s' % (cmd, repr(args)), file = sys.stderr)
	cursor.execute(cmd, args)
	db.commit()
	ret = cursor.fetchall()
	if debug_db:
		print('db returns: %s' % repr(ret), file = sys.stderr)
	return ret
# }}}

def read1(cmd, *args): # {{{
	return [x[0] for x in read(cmd, *args)]
# }}}
# }}}

# Setting up the database. {{{
def setup_prefix(prefix): # {{{
	'''Set the global prefix'''
	global global_prefix
	if not have_global_prefix:	# Ignore request if there was an override from the environment.
		assert global_prefix == ''
		global_prefix = prefix
# }}}

def setup_reset(): # {{{
	'''Delete everything in the database.'''
	connect()
	tables = read1('SHOW TABLES')
	for t in tables:
		if not t.startswith(global_prefix):
			continue
		write('DROP TABLE ' + t)
# }}}

def setup(clean = False, user = True): # {{{
	'''Create tables; optionally remove obsolete tables. Add a user table if user is True and it is not in defs.'''
	connect()
	if os.path.isfile(tabledefs):
		defs = {key.strip(): value.strip() for key, value in (x.split('=', 1) for x in open(tabledefs).read().split('\n') if '=' in x and not x.strip().startswith('#'))}
	else:
		defs = {}
	if user and 'user' not in defs:
		defs['user'] = 'name VARCHAR(255), password VARCHAR(255), email VARCHAR(255)'
	tables = read1('SHOW TABLES')
	if clean:
		for t in tables:
			if not t.startswith(global_prefix):
				continue
			if t[len(global_prefix):] not in defs:
				write('DROP TABLE ' + t)
	for t in defs:
		if global_prefix + t not in tables:
			write('CREATE TABLE %s (%s)' % (global_prefix + t, defs[t]))

	def handle_section(indent, section, state, users, containerlist, playerlist): # {{{
		if len(section) == 0:
			return
		if indent == 0:
			user = section['user']
			if user not in users:
				email = section['email']
				password = section['password']
				setup_add_user(user, email, password)
			state[0] = user
			containerlist[:] = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(user) + '_containers'))

		elif indent == 1:
			if 'game' in section:
				game = section['game']
				if game not in containerlist:
					game_name = section['game_name']
					password = section['password']
					containers = _tabsplit(section.get('containers', ''))
					setup_add_game(state[0], [game] + containers, game_name, password)
				state[1] = game
				playerlist[:] = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(state[0]) + '_' + mangle_name(game) + '_player'))
			else:
				player = section['player']
				url = section['url']
				containers = _tabsplit(section.get('containers', ''))
				is_default = int(section['is_default'])
				state[1] = None
				setup_add_player(state[0], player, url, containers, is_default)

		else:
			assert indent == 2
			player = section['player']
			if player not in playerlist:
				password = section['password']
				email = section['email']
				setup_add_managed_player(state[0], state[1], player, email, password)
	# }}}

	if user and os.path.isfile(userdefs):
		users = read1('SELECT name FROM {}'.format(global_prefix + 'user'))
		containerlist = []
		playerlist = []
		state = [None, None]	# current user, current game.
		with open(userdefs) as f:
			current_indent = None
			section = {}
			for line in f:
				if line.strip() == '' or line.strip().startswith('#'):
					handle_section(current_indent, section, state, users, containerlist, playerlist)
					section = {}
					current_indent = None
					continue

				indent = len(line) - len(line.lstrip())
				key, value = line.split(':', 1)
				key = key.strip()
				value = value.strip()

				if indent != current_indent:
					handle_section(current_indent, section, state, users, containerlist, playerlist)
					section = {}
					current_indent = indent

				assert key not in section
				section[key] = value

			handle_section(current_indent, section, state, users, containerlist, playerlist)
# }}}

# User management. {{{
def setup_add_user(user, email, password = None): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) != 0:
		print('not creating duplicate user %s' % user, file = sys.stderr)
		return 'Registration failed: user name already exists.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, email, password) VALUES (%s, %s, %s)'.format(global_prefix + 'user'), user, email, crypt.crypt(password))
	write('CREATE TABLE %s (name VARCHAR(255) NOT NULL PRIMARY KEY, count INT)' % (global_prefix + mangle_name(user) + '_containers'))
	write('CREATE TABLE %s (game VARCHAR(255) NOT NULL PRIMARY KEY, name VARCHAR(255), password VARCHAR(255), containers VARCHAR(255))' % (global_prefix + mangle_name(user) + '_game'))
	write('CREATE TABLE %s (player VARCHAR(255) NOT NULL PRIMARY KEY, url VARCHAR(255), containers VARCHAR(255), is_default TINYINT(1))' % (global_prefix + mangle_name(user) + '_player'))
	return None
# }}}

def setup_remove_user(user): # {{{
	connect()
	containers = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(user) + '_containers'))
	for container in containers:
		setup_remove_container(user, container)
	write('DELETE FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
# }}}

def setup_list_users(): # {{{
	connect()
	return [{'name': name, 'email': email} for name, email in read('SELECT name, email FROM {}'.format(global_prefix + 'user'))]
# }}}
# }}}

# Container management. {{{
def _incref(user, container): # {{{
	assert container != ''
	count = read1('SELECT count FROM {} WHERE name = %s'.format(global_prefix + user + '_containers'), container)
	if len(count) == 0:
		write('INSERT INTO {} (name, count) VALUES (%s, %s)'.format(global_prefix + user + '_containers'), container, 1)
	else:
		write('UPDATE {} SET count = %s WHERE name = %s'.format(global_prefix + user + '_containers'), count[0] + 1, container)
# }}}

def _decref(user, container, remove_orphans): # {{{
	count = read1('SELECT count FROM {} WHERE name = %s'.format(global_prefix + user + '_containers'), container)[0]
	if count <= 1 and remove_orphans:
		# Remove this container.
		tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + user + '_' + mangle_name(container) + '_')]
		for table in tables:
			write('DROP TABLE {}'.format(table))
		write('DELETE FROM {} WHERE name = %s'.format(global_prefix + user + '_containers'), container)
	else:
		write('UPDATE {} SET count = %s'.format(global_prefix + user + '_containers'), count - 1)
# }}}

def setup_list_containers(user): # {{{
	connect()
	data = read('SELECT name, count FROM {}'.format(global_prefix + mangle_name(user) + '_containers'))
	return [{'name': name, 'count': count} for name, count in data]
# }}}
# }}}

# Game management (for login_game()). {{{
def setup_add_game(user, containers, game_name, password = None): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('not creating game for nonexistent user %s' % user, file = sys.stderr)
		return 'Game registration failed: user does not exist.'
	game = containers[0]
	thisgame = read1('SELECT game FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_game'), game)
	if len(thisgame) != 0:
		print('not creating duplicate game %s' % game, file = sys.stderr)
		return 'Game registration failed: game already exists.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for game %s of user %s: ' % (game, user), stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	for container in containers:
		_incref(user, container)
	write('INSERT INTO {} (game, name, password, containers) VALUES (%s, %s, %s, %s)'.format(global_prefix + mangle_name(user) + '_game'), game, game_name, crypt.crypt(password), '\t'.join(containers[1:]))
	write('CREATE TABLE %s (name VARCHAR(255) NOT NULL PRIMARY KEY, password VARCHAR(255), email VARCHAR(255))' % (global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'))
	return None
# }}}

def setup_update_game(user, containers, game_name, password = None, remove_orphans = True): # {{{
	connect()
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % player, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	oldcontainers = read1('SELECT containers FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_game'), containers[0])
	for container in old_containers:
		if container not in containers:
			_decref(user, container, remove_orphans)
	for container in containers:
		if container not in old_containers:
			_incref(user, container)
	write('UPDATE {} SET game = %s, name = %s, password = %s, containers = %s)'.format(global_prefix + mangle_name(user) + '_user'), containers[0], game_name, crypt.crypt(password), '\t'.join(containers[1:]))
	return None
# }}}

def setup_remove_game(user, game, remove_orphans = True): # {{{
	connect()
	players = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'))
	for player in players:
		setup_remove_player(user, game, player)
	containers = read1('SELECT containers FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_containers'), game)[0]
	for container in containers:
		_decref(user, container)
	write('DROP TABLE %s' % (global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'))
	write('DELETE FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_containers'), game)
# }}}

def setup_list_games(user): # {{{
	connect()
	data = read('SELECT game, name, containers FROM {}'.format(global_prefix + mangle_name(user) + '_game'))
	return [{'game': game, 'name': name, 'containers': _tabsplit(containers)} for game, name, containers in data]
# }}}
# }}}

# Remote player management (for connect()). {{{
def setup_add_player(user, player, url, containers, is_default): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) != 1:
		print('not creating player for unknown user %s' % user, file = sys.stderr)
		return 'Registration failed: user does not exist.'
	oldcontainers = read1('SELECT containers FROM {} WHERE player = %s'.format(global_prefix + mangle_name(user) + '_player'), player)
	if len(oldcontainers) > 0:
		print('not creating duplicate player %s : %s for game %s @ %s' % (user, player, containers[0], url), file = sys.stderr)
		return 'Not creating duplicate player %s : %s for game %s @ %s' % (user, player, containers[0], url)
	if is_default != 0:
		write('UPDATE {} SET is_default = 0 WHERE url = %s'.format(global_prefix + mangle_name(user) + '_player'), url)
	for container in containers:
		_incref(user, container)
	write('INSERT INTO {} (player, url, containers, is_default) VALUES (%s, %s, %s, %s)'.format(global_prefix + mangle_name(user) + '_player'), player, url, '\t'.join(containers), int(is_default))
	return None
# }}}

def setup_update_player(user, player, url, containers, is_default, remove_orphans = True): # {{{
	connect()
	if is_default:
		write('UPDATE {} SET is_default = 0 WHERE url = %s'.format(global_prefix + mangle_name(user) + '_player'), url)
	oldcontainers = read1('SELECT containers FROM {} WHERE player = %s'.format(global_prefix + mangle_name(user) + '_player'), player)
	if len(oldcontainers) > 0:
		oldcontainers = _tabsplit(oldcontainers[0])
	for container in oldcontainers:
		if container in containers:
			continue
		_decref(user, container, remove_orphans)
	for container in containers:
		if container in oldcontainers:
			continue
		_incref(user, container)
	write('UPDATE {} SET player = %s, url = %s, containers = %s, is_default = %s'.format(global_prefix + mangle_name(user) + '_player'), player, url, '\t'.join(containers), int(is_default))
	return None
# }}}

def setup_remove_player(user, player, remove_orphans = True): # {{{
	connect()
	containers = read1('SELECT containers FROM {} WHERE player = %s'.format(global_prefix + mangle_name(user) + '_player'), player)
	if len(containers) > 0:
		containers = _tabsplit(containers[0])
	for container in containers:
		_decref(user, container, remove_orphans)
	write('DELETE FROM {} WHERE player = %s'.format(global_prefix + mangle_name(user) + '_player'), player)
# }}}

def setup_list_players(user, url = None): # {{{
	connect()
	if url is None:
		data = read('SELECT player, url, containers, is_default FROM {}'.format(global_prefix + mangle_name(user) + '_player'))
		return [{'player': player, 'url': url, 'containers': _tabsplit(containers), 'is_default': bool(is_default)} for player, url, containers, is_default in data]
	else:
		data = read('SELECT player, containers, is_default FROM {} WHERE url = %s'.format(global_prefix + mangle_name(user) + '_player'), url)
		return [{'player': player, 'containers': _tabsplit(containers), 'is_default': bool(is_default)} for player, containers, is_default in data]
# }}}

def setup_get_player(user, url, player): # {{{
	connect()
	return _tabsplit(read1('SELECT containers FROM {} WHERE url = %s AND player = %s'.format(global_prefix + mangle_name(user) + '_player'), url, player)[0])
# }}}
# }}}

# Managed player management (for login_player()). {{{
def setup_add_managed_player(user, game, player, email, password = None): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) != 1:
		print('not creating player for unknown user %s' % user, file = sys.stderr)
		return 'Registration failed: user does not exist.'
	players = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'), player)
	if len(players) > 0:
		print('not creating duplicate player %s : %s for game %s' % (user, player, game), file = sys.stderr)
		return 'Not creating duplicate player %s : %s for game %s' % (user, player, game)
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, password, email) VALUES (%s, %s, %s)'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'), player, crypt.crypt(password), email)
	return None
# }}}

def setup_update_managed_player(user, game, player, email, password = None): # {{{
	connect()
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('UPDATE {} SET name = %s, password = %s, email = %s'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'), player, crypt.crypt(password), email)
	return None
# }}}

def setup_remove_managed_player(user, game, player): # {{{
	connect()
	write('DELETE FROM {} WHERE name = %s'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'), player)
	tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_' + mangle_name(player) + '_')]
	for table in tables:
		write('DROP TABLE %s' % table)
# }}}

def setup_list_managed_players(user, game): # {{{
	connect()
	data = read('SELECT name, email FROM {}'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'))
	return [{'name': name, 'email': email} for name, email in data]
# }}}
# }}}
# }}}

def authenticate_user(user, password): # {{{
	connect()
	users = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return False
	assert len(users) == 1
	attempt = crypt.crypt(password, users[0])
	if users[0] != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return False
	return True
# }}}

def authenticate_game(user, game, password): # {{{
	connect()
	users = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return False
	containers = read('SELECT password, containers FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_game'), game)
	if len(containers) == 0:
		print('Login failed: no such game.', file = sys.stderr)
		return False
	assert len(containers) == 1
	attempt = crypt.crypt(password, containers[0][0])
	if containers[0][0] != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return False
	return _tabsplit(containers[0][1])
# }}}

def authenticate_player(user, game, player, password): # {{{
	connect()
	users = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return False
	containers = read1('SELECT password FROM {} WHERE game = %s'.format(global_prefix + mangle_name(user) + '_game'), game)
	if len(containers) == 0:
		print('Login failed: no such game.', file = sys.stderr)
		return False
	players = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + mangle_name(user) + '_' + mangle_name(game) + '_player'), player)
	if len(players) == 0:
		print('Login failed: no such player.', file = sys.stderr)
		return False
	assert len(players) == 1
	attempt = crypt.crypt(password, players[0])
	if players[0] != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return False
	return True
# }}}

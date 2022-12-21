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

def mktable(user_id, game_id, player, table): # {{{
	'Create SQL table name'
	return global_prefix + user_id + '_' + game_id + '_' + player + '_' + table
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

	def handle_section(indent, section, state, users, gamelist, playerlist): # {{{
		if len(section) == 0:
			return
		if indent == 0:
			user = section['user']
			if user not in users:
				email = section['email']
				password = section['password']
				setup_add_user(user, email, password)
			state[0] = user
			gamelist[:] = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(user) + '_games'))

		elif indent == 1:
			game = section['game']
			if game not in gamelist:
				game_name = section['game_name']
				password = section['password']
				games = section.get('games', '').split('\t')
				setup_add_game(state[0], [game] + games, game_name, password)
			state[1] = game
			playerlist[:] = read1('SELECT name FROM {}'.format(global_prefix + mangle_name(state[0]) + '_' + mangle_name(game) + '_player'))

		else:
			assert indent == 2
			player = section['player']
			if player not in playerlist:
				password = section['password']
				email = section['email']
				setup_add_player(state[0], state[1], player, email, password)
	# }}}

	if user and os.path.isfile(userdefs):
		users = read1('SELECT name FROM {}'.format(global_prefix + 'user'))
		gamelist = []
		playerlist = []
		state = [None, None]	# current user, current game.
		with open(userdefs) as f:
			current_indent = None
			section = {}
			for line in f:
				if line.strip() == '' or line.strip().startswith('#'):
					handle_section(current_indent, section, state, users, gamelist, playerlist)
					section = {}
					current_indent = None
					continue

				indent = len(line) - len(line.lstrip())
				key, value = line.split(':', 1)
				key = key.strip()
				value = value.strip()

				if indent != current_indent:
					handle_section(current_indent, section, state, users, gamelist, playerlist)
					section = {}
					current_indent = indent

				assert key not in section
				section[key] = value

			handle_section(current_indent, section, state, users, gamelist, playerlist)
# }}}

def setup_add_user(user, email, password = None): # {{{
	connect()
	user = mangle_name(user)
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
	write('CREATE TABLE %s (name VARCHAR(255) NOT NULL PRIMARY KEY)' % (global_prefix + user + '_games'))
	write('CREATE TABLE %s (game_id VARCHAR(255) NOT NULL PRIMARY KEY, password VARCHAR(255), game_name VARCHAR(255), games VARCHAR(255))' % (global_prefix + user + '_user'))
	return None
# }}}

def setup_add_game(user, games, game_name, password = None): # {{{
	connect()
	user = mangle_name(user)
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('not creating game for nonexistent user %s' % user, file = sys.stderr)
		return 'Game registration failed: user does not exist.'
	game = mangle_name(games[0])
	thisgame = read1('SELECT game_id FROM {} WHERE game_id = %s'.format(global_prefix + user + '_user'), game)
	if len(thisgame) != 0:
		print('not creating duplicate game %s' % game, file = sys.stderr)
		return 'Game registration failed: game already exists.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for game %s of user %s: ' % (game, user), stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (game_id, password, game_name, games) VALUES (%s, %s, %s, %s)'.format(global_prefix + user + '_user'), game, crypt.crypt(password), game_name, '\t'.join(mangle_name(g) for g in games[1:]))
	write('CREATE TABLE %s (name VARCHAR(255) NOT NULL PRIMARY KEY, password VARCHAR(255), email VARCHAR(255))' % (global_prefix + user + '_' + game + '_player'))
	return None
# }}}

def setup_update_game(user, games, game_name, password = None): # {{{
	connect()
	user = mangle_name(user)
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % player, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('UPDATE {} SET game_id = %s, password = %s, game_name = %s, games = %s)'.format(global_prefix + user + '_user'), mangle_name(games[0]), crypt.crypt(password), game_name, '\t'.join(mangle_name(g) for g in games[1:]))
	return None
# }}}

def setup_add_player(user, game_id, player, email, password = None): # {{{
	connect()
	user = mangle_name(user)
	game_id = mangle_name(game_id)
	player = mangle_name(player)
	users = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) != 1:
		print('not creating player for unknown user %s' % user, file = sys.stderr)
		return 'Registration failed: user does not exist.'
	players = read1('SELECT name FROM {} WHERE name = %s'.format(global_prefix + user + '_' + game_id + '_player'), player)
	if len(players) > 0:
		print('not creating duplicate player %s for game_id %s' % (user, game_id), file = sys.stderr)
		return 'Not creating duplicate player %s for game_id %s' % (user, game_id)
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, password, email) VALUES (%s, %s, %s)'.format(global_prefix + user + '_' + game_id + '_player'), player, crypt.crypt(password), email)
	return None
# }}}

def setup_update_player(user, game_id, player, email, password = None): # {{{
	connect()
	user = mangle_name(user)
	game_id = mangle_name(game_id)
	player = mangle_name(player)
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('UPDATE {} SET name = %s, password = %s, email = %s'.format(global_prefix + user + '_' + game_id + '_player'), player, crypt.crypt(password), email)
	return None
# }}}

def setup_remove_user(user): # {{{
	connect()
	user = mangle_name(user)
	games = read1('SELECT name FROM {}'.format(global_prefix + user + '_games'))
	for game in games:
		setup_remove_game(user, game)
	write('DELETE FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
# }}}

def setup_remove_game(user, game): # {{{
	connect()
	user = mangle_name(user)
	game = mangle_name(game)
	players = read1('SELECT name FROM {}'.format(global_prefix + user + '_' + game + '_player'))
	for player in players:
		setup_remove_player(user, game, player)
	write('DROP TABLE %s' % (global_prefix + user + '_player'))
	write('DELETE FROM {} WHERE name = %s'.format(global_prefix + user + '_games'), game)
# }}}

def setup_remove_player(user, game, player): # {{{
	connect()
	user = mangle_name(user)
	game = mangle_name(game)
	player = mangle_name(player)
	write('DELETE FROM {} WHERE name = %s'.format(global_prefix + user + '_' + game + '_player'), player)
	tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + user + '_' + game + '_' + player + '_')]
	for table in tables:
		write('DROP TABLE %s' % table)
# }}}
# }}}

def authenticate_user(user, password): # {{{
	connect()
	user = mangle_name(user)
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

def authenticate_game(user, game_id, password): # {{{
	connect()
	user = mangle_name(user)
	game_id = mangle_name(game_id)
	users = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return False
	games = read('SELECT password, games FROM {} WHERE game_id = %s'.format(global_prefix + user + '_user'), game_id)
	if len(games) == 0:
		print('Login failed: no such game.', file = sys.stderr)
		return False
	assert len(games) == 1
	attempt = crypt.crypt(password, games[0][0])
	if games[0][0] != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return False
	return games[0][1].split('\t')
# }}}

def authenticate_player(user, game_id, player, password): # {{{
	connect()
	user = mangle_name(user)
	game_id = mangle_name(game_id)
	player = mangle_name(player)
	users = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return False
	games = read1('SELECT password FROM {} WHERE game_id = %s'.format(global_prefix + user + '_user'), game_id)
	if len(games) == 0:
		print('Login failed: no such game.', file = sys.stderr)
		return False
	players = read1('SELECT password FROM {} WHERE name = %s'.format(global_prefix + user + '_' + game_id + '_player'), player)
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

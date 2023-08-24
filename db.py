# Imports {{{
import sys
import os
import fhs
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

global_prefix = os.environ.get('DBPREFIX')
have_global_prefix = global_prefix is not None
if global_prefix is None:
	global_prefix = ''

db = None
cursor = None
database = None

fhs.module_info('db', 'database handling', '0.1', 'Bas Wijnen <wijnen@debian.org>')
fhs.module_option('db', 'prefix', 'global prefix for all database tables', default = '')

@fhs.atinit
def init():
	global config, userdefs, tabledefs
	# The config file is in windows ini format (lines with key = value). # for comments. Empty lines allowed.
	def find_config(env_key, default_filename):
		e = os.environ.get(env_key)
		if e is None:
			return fhs.read_data(default_filename, opened = False)
		return e

	# Keys are host, user, password, database. All are required. No others are allowed.
	config = find_config('DBCONFIG', 'db.ini')

	# These files can be used using the setup functions. This is optional.
	userdefs = find_config('DBUSER', 'db-user.ini')
	tabledefs = find_config('DBTABLES', 'db-tables.ini')
	values, present = fhs.module_get_config('db', True)
	if have_global_prefix:
		if present['prefix']:
			print('DB prefix from commandline is ignored because DBPREFIX is defined in environment', file = sys.stderr)
	else:
		global_prefix = values['prefix']
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

# Main accesssing functions. {{{
def write(cmd, *args): # {{{
	if debug_db:
		print('db writing: %s%s)' % (cmd, repr(args)), file = sys.stderr)
	try:
		cursor.execute(cmd, args)
		db.commit()
	except pymysql.OperationalError:
		print('Error ignored on write')
		connect(True)
		cursor.execute(cmd, args)
		db.commit()
# }}}

def read(cmd, *args): # {{{
	if debug_db:
		print('db reading: %s%s' % (cmd, repr(args)), file = sys.stderr)
	try:
		cursor.execute(cmd, args)
		db.commit()
	except pymysql.OperationalError:
		print('Error ignored on read')
		connect(True)
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
def setup_reset(): # {{{
	'''Delete everything in the database.'''
	connect()
	tables = read1('SHOW TABLES')
	for t in tables:
		if not t.startswith(global_prefix):
			continue
		write('DROP TABLE ' + t)
# }}}

def setup(clean = False, create_globals = True): # {{{
	'''Create tables; optionally remove obsolete tables. Add a user table if user is True and it is not in defs.'''
	connect()
	if os.path.isfile(tabledefs):
		defs = {key.strip(): value.strip() for key, value in (x.split('=', 1) for x in open(tabledefs).read().split('\n') if '=' in x and not x.strip().startswith('#'))}
	else:
		defs = {}
	if create_globals:
		if 'user' not in defs:
			defs['user'] = (
				'id INT UNIQUE NOT NULL AUTO_INCREMENT, ' +
				'name VARCHAR(255) NOT NULL PRIMARY KEY, ' +
				'fullname VARCHAR(255) NOT NULL, ' +
				'password VARCHAR(255) NOT NULL, ' +
				'email VARCHAR(255) NOT NULL'
			)
		if 'game' not in defs:
			defs['game'] = (
				'id INT PRIMARY KEY NOT NULL AUTO_INCREMENT, ' +
				'user INT NOT NULL, ' +
				'name VARCHAR(255) NOT NULL, ' +
				'fullname VARCHAR(255) NOT NULL, ' +
				'password VARCHAR(255) NOT NULL'
			)
		if 'player' not in defs:
			defs['player'] = (
				'id INT PRIMARY KEY NOT NULL AUTO_INCREMENT, ' +
				'user INT NOT NULL, ' +
				'url VARCHAR(255) NOT NULL, ' +
				'name VARCHAR(255) NOT NULL, ' +
				'fullname VARCHAR(255) NOT NULL, ' +
				'language VARCHAR(255) DEFAULT NULL, ' +
				'is_default INT(1) NOT NULL'
			)
		if 'managed' not in defs:
			defs['managed'] = (
				'id INT PRIMARY KEY NOT NULL AUTO_INCREMENT, ' +
				'game INT, ' +
				'name VARCHAR(255) NOT NULL, ' +
				'fullname VARCHAR(255) NOT NULL, ' +
				'language VARCHAR(255) DEFAULT NULL, ' +
				'password VARCHAR(255) NOT NULL, ' +
				'email VARCHAR(255) NOT NULL'
			)
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

	def handle_section(indent, section, state): # {{{
		# Newline found or indentation changed; handle section.

		if len(section) == 0:
			# Empty section (multiple newlines); ignore.
			return

		if indent == 0:
			# Top level: user definition.
			user = section['user']
			fullname = section['name']
			email = section['email']
			password = section['password']
			if user not in read1('SELECT name FROM {}'.format(global_prefix + 'user')):
				setup_add_user(user, fullname, email, password)
				state['user'] = read1('SELECT id FROM {} WHERE name = %s'.format(global_prefix + 'user'), user)[0]
			else:
				userid = find_user(user)
				setup_update_user(userid, user, fullname, email, password)
				state['user'] = userid

		elif indent == 1:
			# Indented: game or player definition (part of user).
			if 'game' in section:
				game = section['game']
				fullname = section['name']
				password = section['password']
				if game not in [x['name'] for x in setup_list_games(state['user'])]:
					setup_add_game(state['user'], game, fullname, password)
					state['game'] = read1('SELECT id FROM {} WHERE name = %s'.format(global_prefix + 'game'), game)[0]
				else:
					gameid = find_game(state['user'], game)
					setup_update_game(gameid, state['user'], game, fullname, password)
					state['game'] = gameid
			else:
				player = section['player']
				url = section['url']
				fullname = section['name']
				language = section['language']
				is_default = int(section['is_default'])
				state['game'] = None
				setup_add_player(state['user'], url, player, fullname, language, is_default)

		else:
			# Doubly indented: managed player definition.
			assert indent == 2
			player = section['player']
			fullname = section['name']
			password = section['password']
			email = section['email']
			if player in [x['name'] for x in setup_list_managed_players(state['game'])]:
				setup_add_managed_player(state['game'], player, fullname, email, password)
			else:
				setup_update_managed_player(state['user'], state['game'], player, fullname, email, password)
	# }}}

	if create_globals and os.path.isfile(userdefs):
		state = {'user': None, 'game': None}
		with open(userdefs) as f:
			current_indent = None
			section = {}
			for line in f:
				if line.strip() == '' or line.strip().startswith('#'):
					handle_section(current_indent, section, state)
					section = {}
					current_indent = None
					continue

				indent = len(line) - len(line.lstrip())
				key, value = line.split(':', 1)
				key = key.strip()
				value = value.strip()

				if indent != current_indent:
					handle_section(current_indent, section, state)
					section = {}
					current_indent = indent

				assert key not in section
				section[key] = value

			handle_section(current_indent, section, state)
# }}}

# User management. {{{
def find_user(name): # {{{
	users = read1('SELECT id FROM {} WHERE name = %s'.format(global_prefix + 'user'), name)
	if len(users) != 1:
		return None
	return users[0]
# }}}

def setup_add_user(user, fullname, email, password = None): # {{{
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
	write('INSERT INTO {} (name, fullname, email, password) VALUES (%s, %s, %s, %s)'.format(global_prefix + 'user'), user, fullname, email, crypt.crypt(password))
	return None
# }}}

def setup_update_user(userid, name, fullname, email, password): # {{{
	'Update user record. If password is None, keep it as is.'
	connect()
	if userid is None:
		print('not updating nonexistent user %x' % userid, file = sys.stderr)
		return 'Update failed: user id does not exist.'
	ids = read1('SELECT id FROM {} WHERE name = %s'.format(global_prefix + 'user'), name)
	if len(ids) > 0 and ids[0] != userid:
		print('not updating user to existing name %s' % name)
		return 'Update failed: new user name already exists'
	if len(users) > 1:
		# This should never happen, because name is UNIQUE.
		print('not updating user %s, which is defined more than once' % name, file = sys.stderr)
		return 'Update failed: user exists more than once.'
	if password is None:
		write('UPDATE {} SET name = %s, fullname = %s, email = %s WHERE id = %s'.format(global_prefix + 'user'), name, fullname, email, userid)
	else:
		write('UPDATE {} SET name = %s, fullname = %s, email = %s, password = %s WHERE id = %s'.format(global_prefix + 'user'), name, fullname, email, crypt.crypt(password), userid)
	return None
# }}}

def setup_remove_user(userid): # {{{
	connect()
	assert userid is not None
	for game in setup_list_games(userid):
		setup_remove_game(userid, game['id'], True)
	for player in setup_list_players(userid):
		setup_remove_player(userid, player['id'])
	write('DELETE FROM {} WHERE id = %s'.format(global_prefix + 'user'), userid)
# }}}

def setup_list_users(): # {{{
	connect()
	return [{'id': id, 'name': name, 'fullname': fullname, 'email': email} for id, name, fullname, email in read('SELECT id, name, fullname, email FROM {}'.format(global_prefix + 'user'))]
# }}}
# }}}

# Game management (for login_game()). {{{
def find_game(userid, name): # {{{
	games = read1('SELECT id FROM {} WHERE user = %s AND name = %s'.format(global_prefix + 'game'), userid, name)
	if len(games) != 1:
		return None
	return games[0]
# }}}

def setup_add_game(userid, name, fullname, password): # {{{
	connect()
	users = read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'user'), userid)
	if len(users) == 0:
		print('not creating game for nonexistent user %x' % userid, file = sys.stderr)
		return 'Game registration failed: user does not exist.'
	game = read1('SELECT name FROM {} WHERE user = %s AND name = %s'.format(global_prefix + 'game'), userid, name)
	if len(game) != 0:
		print('not creating duplicate game %s' % name, file = sys.stderr)
		return 'Game registration failed: game already exists.'
	write('INSERT INTO {} (user, name, fullname, password) VALUES (%s, %s, %s, %s)'.format(global_prefix + 'game'), userid, name, fullname, crypt.crypt(password))
	return None
# }}}

def setup_update_game(gameid, userid, name, fullname, password): # {{{
	'Update game record. If password is None, keep it as is.'
	connect()
	users = read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'user'), userid)
	if len(users) == 0:
		print('not updating game to nonexistent user %x' % userid, file = sys.stderr)
		return 'Game registration failed: user does not exist.'
	ids = read('SELECT id FROM {} WHERE user = %s AND name = %s'.format(global_prefix + 'game'), userid, name)
	if len(ids) != 0 and gameid != ids[0]:
		print('not updating to existing game %s' % name, file = sys.stderr)
		return 'Game update failed: game already exists.'
	if password is None:
		write('UPDATE {} SET user = %s, name = %s, fullname = %s WHERE id = %s'.format(global_prefix + 'game'), userid, name, fullname, gameid)
	else:
		write('UPDATE {} SET user = %s, name = %s, fullname = %s, password = %s WHERE id = %s'.format(global_prefix + 'game'), userid, name, fullname, crypt.crypt(password), gameid)
	return None
# }}}

def setup_remove_game(gameid): # {{{
	connect()
	for player in setup_list_managed_players(gameid):
		setup_remove_managed_player(player['id'])
	tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + 'g%x_' % gameid)]
	for table in tables:
		write('DROP TABLE %s' % table)
	write('DELETE FROM {} WHERE id = %s'.format(global_prefix + 'game'), gameid)
# }}}

def setup_list_games(userid): # {{{
	connect()
	data = read('SELECT id, name, fullname FROM {} WHERE user = %s'.format(global_prefix + 'game'), userid)
	return [{'id': id, 'name': name, 'fullname': fullname} for id, name, fullname in data]
# }}}
# }}}

# Remote player management (for connect()). {{{
def find_player(userid, url, name): # {{{
	players = read1('SELECT id, fullname, language, is_default FROM {} WHERE user = %s AND url = %s AND name = %s'.format(global_prefix + 'player'), userid, url, name)
	if len(players) != 1:
		return None
	return {'id': players[0][0], 'name': players[0][1], 'language': players[0][2], 'is_default': players[0][3]}
# }}}

def setup_add_player(userid, url, name, fullname, language, is_default): # {{{
	connect()
	# Check that user exists.
	ids = read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'user'), userid)
	if len(ids) != 1:
		print('not creating player for unknown user %x' % userid, file = sys.stderr)
		return 'Registration failed: user does not exist.'
	# Check that player does not exist yet.
	ids = read1('SELECT id FROM {} WHERE url = %s AND name = %s'.format(global_prefix + 'player'), url, name)
	if len(ids) > 0:
		print('not creating duplicate player %x for game %s @ %s' % (userid, name, url), file = sys.stderr)
		return 'Not creating duplicate player %x for game %s @ %s' % (userid, name, url)
	# If default is set, clear any other default that was set.
	if is_default != 0:
		write('UPDATE {} SET is_default = 0 WHERE user = %s AND url = %s'.format(global_prefix + 'player'), userid, url)
	# Insert row in table.
	write('INSERT INTO {} (user, url, name, fullname, is_default) VALUES (%s, %s, %s, %s, %s)'.format(global_prefix + 'player'), userid, url, name, fullname, int(is_default))
	return None
# }}}

def setup_update_player(playerid, userid, url, name, fullname, language, is_default): # {{{
	connect()
	if len(read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'player'), playerid)) == 0:
		print('unknown player')
		return 'unknown player'
	# Check that new user exists.
	if len(read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'user'), userid)) != 1:
		print('not updating player: new user does not exist.')
		return 'Update failed: new user does not exist.'
	# Check that name is not valid for user yet.
	ids = read1('SELECT id FROM {} WHERE user = %s AND name = %s'.format(global_prefix + 'player'), userid, name)
	if len(ids) > 0 and ids[0] != playerid:
		print('not updating player: new name already exists.')
		return 'Update failed: new name already exists.'
	# If default is now set: clear all other defaults.
	if is_default:
		write('UPDATE {} SET is_default = 0 WHERE user = %s AND url = %s'.format(global_prefix + 'player'), userid, url)
	# Update table row.
	write('UPDATE {} SET user = %s, url = %s, name = %s, fullname = %s, language = %s, is_default = %s'.format(global_prefix + 'player'), user, url, name, fullname, language, int(is_default))
	return None
# }}}

def setup_remove_player(playerid): # {{{
	connect()
	tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + 'p%x_' % playerid)]
	for table in tables:
		write('DROP TABLE %s' % table)
	write('DELETE FROM {} WHERE id = %s'.format(global_prefix + 'player'), playerid)
# }}}

def setup_list_players(userid, url = None): # {{{
	connect()
	if url is None:
		data = read('SELECT id, url, name, fullname, is_default FROM {} WHERE user = %s'.format(global_prefix + 'player'), userid)
		return [{'id': id, 'url': url, 'name': name, 'fullname': fullname, 'is_default': bool(is_default)} for id, url, name, fullname, is_default in data]
	else:
		data = read('SELECT id, name, fullname, is_default FROM {} WHERE user = %s AND url = %s'.format(global_prefix + 'player'), userid, url)
		return [{'id': id, 'name': name, 'fullname': fullname, 'is_default': bool(is_default)} for id, name, fullname, is_default in data]
# }}}

def setup_get_default_player(userid, url): # {{{
	connect()
	# Find row that is marked as default.
	data = read('SELECT id, name, fullname FROM {} WHERE user = %s AND url = %s AND is_default = 1'.format(global_prefix + 'player'), userid, url)
	if len(data) != 1:
		# There is no default row. If there is only one row, return it.
		data = read('SELECT id, name, fullname, is_default FROM {} WHERE user = %s AND url = %s ORDER BY name LIMIT 1'.format(global_prefix + 'player'), userid, url)
		if len(data) != 1:
			# There are more rows and none of them are default. Fail.
			return None
	# Return the player.
	id, name, fullname = data[0]
	return {'id': id, 'name': name, 'fullname': fullname, 'is_default': True}
# }}}

def setup_get_player(userid, url, name): # {{{
	'''Get player information from the database by player name.'''
	data = read('SELECT id, fullname, language, is_default FROM {} WHERE user = %s AND url = %s AND name = %s'.format(global_prefix + 'player'), userid, url, name)
	if len(data) == 0:
		# Player does not exist.
		return None
	assert len(data) == 1
	id, fullname, language, is_default = data[0]
	return {'id': id, 'user': userid, 'name': name, 'fullname': fullname, 'language': language, 'url': url, 'is_default': is_default}
# }}}
# }}}

# Managed player management (for login_player()). {{{
def find_managed(gameid, name): # {{{
	players = read('SELECT id, fullname, language, email FROM {} WHERE game = %s AND name = %s'.format(global_prefix + 'managed'), gameid, name)
	if len(players) != 1:
		return None
	return {'id': players[0][0], 'name': players[0][1], 'language': players[0][2], 'email': players[0][3]}
# }}}

def setup_add_managed_player(gameid, name, fullname, email, password): # {{{
	connect()
	# Check that game exists.
	if gameid is None:
		print('not creating managed player for unknown game %x' % gameid)
		return 'Not creating managed player for unknown game.'
	# Check that player does not exist yet.
	if len(read1('SELECT id FROM {} WHERE game = %s AND name = %s'.format(global_prefix + 'managed'), gameid, name)) != 0:
		print('not creating duplicate player %s for game %x' % (name, gameid), file = sys.stderr)
		return 'Not creating duplicate player %s for game %x' % (name, gameid)
	write('INSERT INTO {} (game, name, fullname, email, password) VALUES (%s, %s, %s, %s, %s)'.format(global_prefix + 'managed'), gameid, name, fullname, email, crypt.crypt(password))
	return None
# }}}

def setup_update_managed_player(managedid, gameid, name, fullname, language, email, password): # {{{
	connect()
	# Check that the new game exists.
	if managedid is None or gameid is None or len(read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'game'), gameid)) != 1:
		print('not updating managed player to unknown game %x' % gameid)
		return 'Not updating managed player to unknown game.'
	# Check that player does not exist yet.
	ids = read1('SELECT id FROM {} WHERE game = %s AND name = %s'.format(global_prefix + 'managed'), gameid, name)
	if len(ids) > 0 and ids[0] != managedid:
		print('not updating duplicate player %s for game %x' % (name, gameid), file = sys.stderr)
		return 'Not updating duplicate player %s for game %x' % (name, gameid)
	if password is None:
		write('UPDATE {} SET game = %s, name = %s, fullname = %s, language = %s, email = %s WHERE id = %s'.format(global_prefix + 'managed'), gameid, name, fullname, language, email, managedid)
	else:
		write('UPDATE {} SET game = %s, name = %s, fullname = %s, language = %s, email = %s, password = %s WHERE id = %s'.format(global_prefix + 'managed'), gameid, name, fullname, language, email, crypt.crypt(password), managedid)
	return None
# }}}

def setup_remove_managed_player(managedid): # {{{
	connect()
	tables = [x for x in read1('SHOW TABLES') if x.startswith(global_prefix + 'm%x_' % managedid)]
	for table in tables:
		write('DROP TABLE %s' % table)
	write('DELETE FROM {} WHERE managedid = %s'.format(global_prefix + 'managed'), managedid)
# }}}

def setup_list_managed_players(gameid): # {{{
	connect()
	data = read('SELECT id, name, fullname, email FROM {} WHERE game = %s'.format(global_prefix + 'managed'), gameid)
	return [{'id': id, 'name': name, 'fullname': fullname, 'email': email} for id, name, fullname, email in data]
# }}}
# }}}
# }}}

def authenticate_user(name, password): # {{{
	'Check user credentials. Return user dict on success, None on failure.'
	connect()
	data = read('SELECT id, fullname, email, password FROM {} WHERE name = %s'.format(global_prefix + 'user'), name)
	if len(data) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return None
	assert len(data) == 1
	id, fullname, email, stored_password = data[0]
	attempt = crypt.crypt(password, stored_password)
	if stored_password != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return None
	return {'id': id, 'name': name, 'fullname': fullname, 'email': email}
# }}}

def authenticate_game(username, name, password): # {{{
	'Check game credentials. Return game dict on success, None on failure.'
	connect()
	users = read1('SELECT id FROM {} WHERE name = %s'.format(global_prefix + 'user'), username)
	if len(users) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		return None
	games = read('SELECT id, fullname, password FROM {} WHERE user = %s AND name = %s'.format(global_prefix + 'game'), users[0], name)
	if len(games) != 1:
		print('Login failed: no such game', file = sys.stderr)
		return None
	id, fullname, stored_password = games[0]
	attempt = crypt.crypt(password, stored_password)
	if stored_password != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return None
	return {'id': id, 'user': users[0], 'name': name, 'fullname': fullname}
# }}}

def authenticate_player(gameid, name, password): # {{{
	'Check managed player credentials. Return player dict on success, None on failure.'
	connect()
	games = read1('SELECT id FROM {} WHERE id = %s'.format(global_prefix + 'game'), gameid)
	if len(games) != 1:
		print('Login failed: no such game.', file = sys.stderr)
		return None
	data = read('SELECT id, fullname, email, language, password FROM {} WHERE game = %s AND name = %s'.format(global_prefix + 'managed'), gameid, name)
	if len(data) == 0:
		print('Login failed: no such player.', file = sys.stderr)
		return None
	assert len(data) == 1
	id, fullname, email, language, stored_password = data[0]
	attempt = crypt.crypt(password, stored_password)
	if stored_password != attempt:
		print('Login failed: incorrect password.', file = sys.stderr)
		return None
	return {'id': id, 'game': gameid, 'name': name, 'fullname': fullname, 'email': email, 'language': language}
# }}}

# vim: set foldmethod=marker :

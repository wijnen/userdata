# vim: set foldmethod=marker :

# Imports {{{
import sys
import os
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
create database $database;
create user '$user'@'$host' identified by '$password';
grant all privileges on $database.* to '$user'@'$host';
flush privileges;
EOF
}}}'''

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
def setup_reset(): # {{{
	'''Delete everything in the database.'''
	connect()
	tables = read1('SHOW TABLES')
	for t in tables:
		write('DROP TABLE ' + t)
# }}}

def setup(clean = False, user = True, table = 'user'): # {{{
	'''Create tables; optionally remove obsolete tables. Add a user table if user is True and it is not in defs.'''
	connect()
	if os.path.isfile(tabledefs):
		defs = {key.strip(): value.strip() for key, value in (x.split('=', 1) for x in open(tabledefs).read().split('\n') if '=' in x and not x.strip().startswith('#'))}
	else:
		defs = {}
	if user and 'user' not in defs:
		defs['user'] = 'name VARCHAR(255), password VARCHAR(255), game_id VARCHAR(255), games VARCHAR(255), email VARCHAR(255)'
	tables = read1('SHOW TABLES')
	if clean:
		for t in tables:
			if t not in defs:
				write('DROP TABLE %s', t)
	for t in defs:
		if t not in tables:
			write('CREATE TABLE %s (%s)' % (t, defs[t]))
	if user and os.path.isfile(userdefs):
		users = read1('SELECT name FROM {}'.format(table))
		current = None
		with open(userdefs) as f:
			for line in f:
				if not line.startswith('\t'):
					current, email, password = line.strip().split(':')
					if current not in users:
						setup_add_user(current, email, password, table)
				else:
					assert current is not None
					game_id, games, password = line[1:].strip().split(':')
					games = games.split('\t')
					if current not in users:
						setup_add_user(current, None, password, table, game_id = game_id, games = games)
# }}}

def setup_add_user(user, email, password = None, table = 'user', game_id = None, games = None): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s AND game_id = %s'.format(table), user, game_id)
	if len(users) > 0:
		print('not creating duplicate user %s' % user, file = sys.stderr)
		return 'Registration failed: user name already exists.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, email, password, game_id, games) VALUES (%s, %s, %s, %s, %s)'.format(table), user, email, crypt.crypt(password), game_id, '\t'.join(games) if games is not None else None)
	return None
# }}}

def setup_add_game(user, game_id, games, password = None, table = 'user', email = None): # {{{
	connect()
	users = read('SELECT name, game_id FROM {} WHERE name = %s'.format(table), user)
	if len(users) == 0:
		print('not creating game for nonexistent user %s' % user, file = sys.stderr)
		return 'Game registration failed: user does not exist.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % player, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	assert game_id is not None
	assert games is not None
	assert not any(u[1] == game_id for u in users)
	write('INSERT INTO {} (name, email, password, game_id, games) VALUES (%s, %s, %s, %s, %s)'.format(table), user, email, crypt.crypt(password), game_id, '\t'.join(games))
	return None
# }}}

def setup_add_player(user, game_id, player, password = None, table = 'user'): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s AND game_id = %s'.format(table), user, game_id)
	if len(users) != 1:
		print('not creating player for unknown user %s or game_id %s' % (user, game_id), file = sys.stderr)
		return 'Registration failed: user or game_id does not exist.'
	# FIXME
	players = read1('SELECT user FROM {} WHERE name = %s AND game_id = %s'.format(table), user, game_id)
	if len(players) > 0:
		print('not creating duplicate player %s for game_id %s' % (user, game_id), file = sys.stderr)
		return 'Not creating duplicate player %s for game_id %s' % (user, game_id)
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, password, game_id, game1, game2) VALUES (%s, %s, %s, %s, %s)'.format(table), user, crypt.crypt(password), game_id, game1, game2)
	return None
# }}}

def setup_remove_user(user, table = 'user'): # {{{
	connect()
	write('DELETE FROM {} WHERE name = %s'.format(table), user)
# }}}
# }}}

def setup_remove_player(player, table): # {{{
	connect()
	write('DELETE FROM {} WHERE name = %s'.format(table), player)
# }}}
# }}}

def authenticate(user, password, game_id, table): # {{{
	connect()
	if game_id is None:
		stored = read('SELECT password, game_id, games FROM {} WHERE name = %s AND game_id IS NULL'.format(table), user)
	else:
		stored = read('SELECT password, game_id, games FROM {} WHERE name = %s AND game_id = %s'.format(table), user, game_id)
	if len(stored) == 0:
		print('Login failed: no such user.', file = sys.stderr)
		raise PermissionError('Authentication failed.')
	assert len(stored) == 1
	attempt = crypt.crypt(password, stored[0][0])
	if stored[0][0] != crypt.crypt(password, stored[0][0]):
		print('Login failed: incorrect password.', file = sys.stderr)
		raise PermissionError('Authentication failed.')
	if stored[0][2] is None:
		return None
	return stored[0][2].split('\t')
# }}}

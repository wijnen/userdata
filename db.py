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

def connect(reconnect = False): # {{{
	'''If the connection is active, nothing happens, unless reconnect is True.'''
	global db, cursor
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
		defs['user'] = 'name VARCHAR(255) PRIMARY KEY, password VARCHAR(255)'
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
		udefs = {key.strip(): value.strip() for key, value in (x.split('=', 1) for x in open(userdefs).read().split('\n') if '=' in x and not x.strip().startswith('#'))}
		for u in udefs:
			if u not in users:
				setup_add_user(u, udefs[u], table)
# }}}

def setup_add_user(user, password = None, table = 'user'): # {{{
	connect()
	users = read1('SELECT name FROM {} WHERE name = %s'.format(table), user)
	if len(users) > 0:
		print('not creating duplicate user %s' % user, file = sys.stderr)
		return 'Registration failed: user name already exists.'
	if password is None:
		if sys.stdin.isatty():
			password = getpass.getpass('Enter password for %s: ' % user, stream = sys.stderr)
		else:
			password = sys.stdin.readline().rstrip('\n').rstrip('\r')
	write('INSERT INTO {} (name, password) VALUES (%s, %s)'.format(table), user, crypt.crypt(password))
	return None
# }}}

def setup_remove_user(user, table = 'user'): # {{{
	connect()
	write('DELETE FROM {} WHERE name=%s'.format(table), user)
# }}}

def authenticate(user, password, table = 'user'): # {{{
	connect()
	stored = read1('SELECT password FROM {} WHERE name=%s'.format(table), user)
	if len(stored) == 0:
		return False
	assert len(stored) == 1
	return stored[0] == crypt.crypt(password, stored[0])
# }}}

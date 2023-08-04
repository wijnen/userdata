# Userdata module; main file (run when called as python3 -m userdata)

# Imports {{{
import sys
import os
import re
import subprocess
import secrets
import fhs
import websocketd
# }}}

fhs.option('userdata', 'name of file containing userdata url, login name, game name and password', default = 'userdata.ini')
config = fhs.init()

# Set up userdata.ini if it does not exist. {{{
if not os.path.exists(config['userdata']):
	print('Setting up new userdata database for this game.', file = sys.stderr)
	url = input('What is the url of the userdata to use? ').rstrip('/')
	assert '.' not in url.split('/')[-1]
	default_websocket = url + '/websocket'
	websocket = input('What is the url of the websocket to the userdata? (Leave empty for %s) ' % default_websocket)
	if websocket.strip() == '':
		websocket = default_websocket
	u = websocketd.RPC(websocket)
	login = input('What is your login name on the userdata? ')
	master_password = input('What is the password for this login name on the userdata? ')
	u.login_user(0, login, master_password)
	games = u.list_games(0)
	print('Existing games:' + ''.join('\n\t%s: %s' % (g['name'], g['fullname']) for g in games), file = sys.stderr)
	game = input('What is the new game name (login id) to use? ').strip()
	if any(g['name'] == game for g in games):
		print('Using existing game.')
		game_password = input('What is the game password? ')
	else:
		fullname = input('What is the full game name? ')
		game_password = secrets.token_hex()
		u.add_game(0, game, fullname, game_password)
	with open(config['userdata'], 'w') as f:
		print('url = ' + url, file = f)
		print('websocket = ' + websocket, file = f)
		print('login = ' + login, file = f)
		print('game = ' + game, file = f)
		print('password = ' + game_password, file = f)
else:
	print('Userdata config found; not replacing.')
# }}}

# Find translations, create pot files, update po files. {{{
# Search tree for files; find:
#	*.py: python source.
#	*.js: javascript source.
#	*.html: html source.
#	no extension with first line #!.*python: python source.
#	Other files: not parsed for strings.
potname = os.path.basename(os.path.abspath(os.curdir)) + os.extsep + 'pot'
source = {'py': [], 'js': [], 'html': []}
def find_files(base):
	for f in os.listdir(base):
		if f.startswith('.'):
			continue
		filename = os.path.join(base, f)
		if os.path.islink(filename):
			continue
		if os.path.isdir(filename):
			find_files(filename)
			continue
		if f.endswith(os.extsep + 'py'):
			source['py'].append(filename)
		elif f.endswith(os.extsep + 'js'):
			source['js'].append(filename)
		elif f.endswith(os.extsep + 'html'):
			source['html'].append(filename)
		elif os.extsep not in f:
			with open(filename) as file:
				l = file.readline()
			if re.match('^#!.*python', l):
				source['py'].append(filename)

find_files(os.curdir)

tmp = fhs.write_temp(dir = True)
for html in source['html']:
	os.makedirs(os.path.join(tmp, os.path.dirname(html)), exist_ok = True)
	with open(html, 'rb') as fi:
		with open(os.path.join(tmp, html), 'wb') as fo:
			for line in fi:
				r = re.match(rb".*class='translate[^>]*>([^<]*)<", line)
				if r is None:
					fo.write(b'\n')
				else:
					fo.write(b"console.info(_('" + r.group(1) + b"');\n")
for js in source['js']:
	os.makedirs(os.path.join(tmp, os.path.dirname(js)), exist_ok = True)
	os.symlink(os.path.abspath(js), os.path.join(tmp, js))

os.makedirs(os.path.join('lang', 'html'), exist_ok = True)
os.makedirs(os.path.join('lang', 'python'), exist_ok = True)
subprocess.run(('xgettext', '--add-comments', '--from-code', 'utf-8', '-o', os.path.abspath(os.path.join('lang', 'html', potname)), '-LJavaScript') + tuple(source['html']) + tuple(source['js']), close_fds = True, cwd = tmp)
fhs.remove_temp(tmp)

subprocess.run(('xgettext', '--add-comments', '-o', os.path.join('lang', 'python', potname), '-LPython') + tuple(source['py']), close_fds = True)
for d in ('html', 'python'):
	dirname = os.path.join('lang', d)
	for po in os.listdir(dirname):
		lang, ext = os.path.splitext(po)
		if ext != os.extsep + 'po':
			continue
		print('Updating %s/%s.po' % (d, lang))
		subprocess.run(('msgmerge', '--update', os.path.join(dirname, po), os.path.join(dirname, potname)), close_fds = True)
# }}}

print('Done', file = sys.stderr)

# vim: set foldmethod=marker :

// Userdata helper.
// This file should be included by C++ programs that want to use the userdata system.
// Before including this file, the game name must be #define'd as GAMENAME.

// Includes {{{
#include <webloop.hh>
// }}}

/* Documentation. {{{

At boot time, userdata object is created. This opens an rpc connection to the local userdata.
The connection is userdata.local.rpc. The data access object is userdata.local.game.

* Managed player login:
- Player connects to game. This results in a PlayerConnection object.
- Game lets local userdata create dcid.
- Player receives dcid from game.
- Player is directed to local userdata; it connects to it.
- Player uses dcid to log in to local userdata.
- After login, local userdata informs game by calling setup_connect_player on the game.
- In response, game sets up the Player object.

* External player login:
- Player connects to game. This results in a PlayerConnection object.
- Player receives gcid from game.
- Player connects to external userdata and logs in.
- Player instructs external userdata to contact game, passing gcid.
- External userdata contacts game, passing gcid. This is done on a new connection (which is a PlayerConnection) or over an existing connection, where it will create a new channel by calling setup_connect.
- Player object is set up.

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
}}} */

/* Translations. {{{
def parse_translation(definition): // {{{
	'''Convert a single po file into a dict.
	definition is a str or file.
	Returns the dict.
	'''
	if not isinstance(definition, bytes):
		with open(definition) as f:
			definition = f.read()
	try:
		data = subprocess.run(('msgfmt', '-o', '-', '-'), input = definition, close_fds = True, stdout = subprocess.PIPE).stdout
		assert len(data) > 0
	except:
		print('Warning: translation could not be read', file = sys.stderr)
		traceback.print_exc()
		return None
	terms = gettext.GNUTranslations()
	terms._parse(io.BytesIO(data))
	// Convert catalog to regular dict, just in case it wasn't.
	ret = {k: v for k, v in terms._catalog.items()}
	// Remove info node.
	del ret['']
	return ret
// }}}

def read_translations(path): // {{{
	'''Read all translations at path.
	path must be the name of a directory where *.po files are stored. Each file translates the same strings into a language. The filename is the language code (e.g. nl.po).
	Returns a dict of language code keys with dicts of translations as values.
	'''
	ret = {}
	if not os.path.isdir(path):
		print('no translations at %s: path does not exist or is not a directory' % path)
		return ret
	print('reading translations, path="%s"' % path)
	for po in os.listdir(path):
		filename = os.path.join(path, po)
		lang, ext = os.path.splitext(po)
		if ext != os.extsep + 'po' or lang.startswith('.') or not os.path.isfile(filename):
			continue
		with open(filename, 'rb') as f:
			data = parse_translation(f.read())
		if data is None:
			continue
		ret[lang] = data
		print('read language: %s' % lang)
	return ret
// }}}

def _(template, *args): // {{{
	'''Translate a string into the currenly selected language.
	This function is not used by the module. It is meant to be imported by the game using:
		from userdata import _, N_
	That way, translatable strings can be marked using _('string').'''
	if template in game_strings_python:
		template = game_strings_python[template]
	else:
		print('Warning: translation for "%s" not found in dictionary' % template, file = sys.stderr)
	// Handle template the same as in javascript.
	def replace(match):
		n = int(match.group(1))
		if not 1 <= n <= len(args):
			print('Warning: translation template "%s" references invalid argument %d' % (template, n), file = sys.stderr)
			return b'[%d]' % n
		return args[n - 1]
	return re.sub(rb'\$(\d)', template, replace)
// }}}

def N_(template): // {{{
	'This function is used to mark translatable strings that should not be translated where they are defined.'
	return template
// }}}
// }}} */

template <class Connection>
class Access { // {{{
	Webloop::RPC <Connection> *socket;
	std::shared_ptr <Webloop::WebInt> channel;
public:
	Access() : socket(nullptr), channel() {}
	Access(Webloop::RPC <Connection> *obj, int channel) : socket(obj), channel(Webloop::WebInt::create(channel)) {}
	friend template <> std::swap <Access <Connection> > (Access <Connection>  &self, Access <Connection>  &other) { // {{{
		std::swap(self.socket, other.socket);
		std::swap(self.channel, other.channel);
	} // }}}
	Access(Access <Connection> &&other) : socket(std::move(other.socket)), channel(std::move(other.channel)) {}
	Access <Connection> &operator=(Access <Connection> &&other) { std::swap(*this, other); }
	void bgcall(std::string const &command, Args args, KwArgs kwargs, BgReply reply = nullptr) {
		auto realargs = args->copy();
		realargs.insert(0, channel);
		socket->bgcall(command, realargs, kwargs, reply);
	}
	Webloop::coroutine fgcall(std::string const &command, Args args, KwArgs kwargs) {
		auto realargs = args->copy();
		realargs.insert(0, channel);
		auto YieldFrom(ret, socket->fgcall(command, realargs, kwargs));
		co_return ret;
	}
}; // }}}

// Commandline options. {{{
struct UserdataConfig {
	Webloop::StringOption userdata;
	Webloop::StringOption game_url;
	Webloop::StringOption default_userdata;
	Webloop::BoolOption allow_local;
	Webloop::BoolOption no_allow_other;
	Webloop::BoolOption allow_new_players;
};
UserdataConfig userdata_config {
	{"userdata", "name of file containing userdata url, login name, game name and password", {}, "userdata.ini"},
	{"game-url", "game url", {}, ""},
	{"default-userdata", "default servers for users to connect to (empty string for locally managed)", {}, ""},
	{"allow-local", "allow locally managed users"},
	{"no-allow-other", "do not allow a non-default userdata server"},
	{"allow-new-players", "allow registering new locally managed users"}
};
// }}}

template <class Player>
class Userdata { // {{{
	/* Games need to include this file and create an instance of this class.
	   The instance will:
	   - Connect to a userdata for its own data and data of managed users.
		The connection is local.rpc; the object to access local data is local.game.
	   - start an RPC server for players to log in to. This is called httpd.
	   When players connect, a PlayerConnection object is created.
	 */
public:
	class PlayerConnection;
	typedef Httpd <PlayerConnection, Userdata <Player> > ServerType;
	typedef ServerType::Args Args;
	typedef ServerType::KwArgs KwArgs;
	typedef ServerType::BgReply BgReply;
	typedef void (*Player::ConnectedCb)();
	typedef void (*Player::DisconnectedCb)();
	class PlayerConnection { // {{{
		// An instance of this class is a connection to a (potential) player.
		RPC <Player> rpc;
		std::string gcid;
		std::string dcid;
		std::string name;
		std::string managed_name;
		int channel;
		Player *player;
		Userdata <Player> *userdata;
		Access data;
		PlayerConnection(ServerType::Connection &connection) : // {{{
				rpc(connection, this),
				gcid(),
				dcid(),
				name(),
				channel(0),
				player(nullptr),
				userdata(connection.httpd.owner),
				data()
		{
			rpc.set_closed_cb(&PlayerConnection::closed);

			// A gcid in the query string is used by an external userdata to connect a player.
			auto c = url.query.find("channel");
			auto g = url.query.find("gcid");
			auto n = url.query.find("name");
			if (c == url.query.end() || g == url.query.end() || n == url.query.end()) {
				// No gcid (or no channel, or no name), so this connection is for a player to log in to this game.
				finish_init()(); // Start the coroutine immediately.
				return;
			}

			// A connection with a gcid should be a userdata providing access to this game for a player.

			// Set player from gcid.
			auto &gcid = g->second;
			auto &channel = c->second;
			auto &name = n->second;

			// setup_connect handles connecting the userdata to the game.
			// This can also be called by the userdata on an existing connection.
			setup_connect(channel, name, nullptr, gcid)();	// Start the coroutine immediately.
		} // }}}

		Webloop::coroutine finish_init(bool logged_out = false) { // {{{
			// Second stage of constructor. This is a separate function so it can yield.
			gcid = create_token();
			while (userdata->pending_gcid.contains(gcid) || userdata->active_gcid.contains(gcid))
				gcid = create_token();
			userdata->pending_gcid[gcid] = this;
			std::string reported_gcid;
			if (!userdata_config.no_allow_other.value)
				reported_gcid = gcid;
			if (userdata_config.allow_local)
				YieldFrom(dcid, userdata->local.game.fgcall("create_dcid", gcid));
			std::shared_ptr <Webloop::WebMap> sent_settings = Webloop::WebMap::create({
				{"allow-local", Webloop::WebBool::create(userdata_config.allow_local.value)},
				{"allow-other", Webloop::WebBool::create(!userdata_config.no_allow_other.value)},
			});
			if (userdata_config.allow_local.value)
				sent_settings["local-userdata"] = Webloop::WebString::create(userdata_config.userdata.value);
			if (logged_out)
				sent_settings["logout"] = Webloop::WebInt::create(1);
			rpc.bgcall("userdata_setup", Webloop::WebVector::create({Webloop::WebString::create(userdata_config.default_userdata.value), Webloop::WebString::create(userdata_config.game_url.value), sent_settings, Webloop::WebString::create(reported_gcid), Webloop::WebString::create(dcid)}));
		} // }}}

		Webloop::coroutine revoke_links() { // {{{
			if (!gcid.empty()) {
				if (name.empty())
					userdata->pending_gcid.pop(gcid);
				else:
					userdata->active_gcid.pop(gcid);
				gcid.clear();
			}
			if (!dcid.empty()) {
				if (name.empty()) {
					auto YieldFrom(unused, userdata->local.game.fgcall("drop_pending_dcid", Webloop::WebVector::create({Webloop::WebString::create(dcid)})));
				}
				else {
					auto YieldFrom(unused, userdata->local.game.fgcall("drop_active_dcid", Webloop::WebVector::create({Webloop::WebString::create(dcid)})));
				}
				dcid.clear();
			}
		} // }}}
		coroutine closed() { // {{{
			auto YieldFrom(unused, revoke_links());
			if (channel != 0) {
				// This is a player connection.
				if (userdata->player.contains(gcid))
					userdata->players.pop(gcid);
				// Notify userdata that user is lost.
				userdata->disconnect(this);
			}
			else {
				// This is a userdata connection.
				// TODO: Kick users of this data.
			}
		} // }}}

		Webloop::coroutine setup_connect(int channel, std::string const &name, std::string const &language, std::string const &gcid): // {{{
			/* Set up new external player on this userdata connection.
			This call is made by a userdata, either at the end of the
			contructor of the connection object, or on a connection that is
			already used for another player. */

			// Check that this is not already a player connection.
			assert(channel != 0);

			auto g = userdata->pending_gcid.find(gcid);
			// Check that the gcid is valid.
			if (g == userdata->pending_gcid.end()) {
				WL_log("invalid gcid in query string");
				throw "invalid gcid";
			}

			// Set up the player.
			auto connection = g->second;
			userdata->active_gcid[gcid] = connection;
			userdata->pending_gcid.erase(g);
			connection->name = name;
			connection->managed_name.clear();
			connection->language = language;

			// Check and set player id.
			assert(connection->channel == 0);
			connection->channel = userdata->next_channel++;

			// FIXME: Set self._player so calls to the userdata server are allowed.
			//assert connection->player in (None, True)
			//connection->player = True

			// Set the userdata.
			// XXX
			connection->... = Access(connection->rpc, channel)
			yield from connection->setup_player(wake)
		// }}}
		
		def _update_strings(self): // {{{
			self._remote.userdata_translate.event(system_strings[self._language] if self._language in system_strings else None, game_strings_html[self._language] if self._language in game_strings_html else None)
		// }}}
		def _setup_player(self, wake): // {{{
			// Handle player setup. This is called both for managed and external players.
			// Initialize db
			assert self._player is None
			player_config = self._settings['server']._player_config
			if player_config is not None:
				yield from self._userdata.setup_db(player_config, wake = wake)

			// Record internal player object in server.
			self._settings['server']._players[self._channel] = self

			// Create user player object and record it in the server.
			try:
				self._player = self._settings['player'](self._gcid, self._name, self._userdata, self._remote, self._managed_name)
			except:
				// Error: close connection.
				print('Unable to set up player settings; disconnecting', file = sys.stderr)
				traceback.print_exc()
				self._remote._websocket_close()
				return
			self._settings['server'].players[self._channel] = self._player

			self._update_strings()
			self._remote.userdata_setup.event(None, None, {'name': self._name, 'managed': self._managed_name})

			try:
				player_init = self._player._init(wake)
				// If _init is a generator, wait for it to finish.
				if type(player_init) is type((lambda: (yield))()):
					yield from player_init
			except:
				// Error: close connection.
				print('Unable to set up player; disconnecting', file = sys.stderr)
				traceback.print_exc()
				self._remote._websocket_close()
		// }}}

		def userdata_logout(self): // {{{
			wake = (yield)
			print('logout')
			self._player = None	// FIXME: close link with userdata as well.
			yield from self._finish_init(logged_out = True, wake = wake)
		// }}}

		def __getattr__(self, attr): // {{{
			if self._player in (None, True):
				raise AttributeError('invalid attribute for anonymous user')
			return getattr(self._player, attr)
		// }}}
	} // }}}
	struct GameConnection { // {{{
		Userdata <Player> *userdata;	// Parent object.
		Webloop::RPC <GameConnection> rpc;
		Access <GameConnection> game;	// Game data access.
		void closed() { Webloop::Loop::get()->stop(); }
		void login_done(std::shared_ptr <Webloop::WebObject> ret) { // {{{
			// login done, enable game access.
			game = Access <GameConnection> (&rpc, 0);

			if (userdata->db_config->size() > 0)
				game.bgcall("setup_db", Webloop::WebVector::create(Webloop::WebInt::create(0), userdata->db_config));
			// TODO: Inform game that connection is active.
		} // }}}
		void login_failed(std::string const &message) { // {{{
			WL_log("Login failed");
			Webloop::Loop::get()->stop();
		} // }}}

		// TODO: Convert setup_connect_player
		Webloop::coroutine setup_connect_player(std::shared_ptr <Webloop::WebVector> args, std::shared_ptr <Webloop::WebMap> kwargs) { // {{{
			// Report successful login of a managed player.
			// XXX What if the player was already logged in?
			assert gcid in PlayerConnection._pending_gcid
			player = PlayerConnection._pending_gcid.pop(gcid)
			PlayerConnection._active_gcid[gcid] = player
			player._managed_name = name
			player._name = fullname
			player._language = language

			assert player._channel is False
			player._channel = self.settings['server']._next_channel
			self.settings['server']._next_channel += 1
			self.settings['userdata'].access_managed_player.bg(wake, channel, player._channel, player._managed_name)
			yield
			player._userdata = Access(self.settings['userdata'], player._channel)

			yield from player._setup_player(wake)
		} // }}}
		typedef void (GameConnection::*Reply)(std::shared_ptr <Webloop::WebObject> ret);
		static std::map <std::string, Webloop::RPC <GameConnection>::Published> published;
		GameConnection(std::string const &service, Userdata *userdata) : // {{{
				userdata(userdata),
				rpc(service, {}, this)
		{
			rpc.set_closed(&GameConnection::closed);
			rpc.set_error(&GameConnection::login_failed);
			rpc.bgcall("login_game", Webloop::WebVector::create(
						Webloop::WebInt::create(0),
						Webloop::WebString(usetup.login),
						Webloop::WebString(usetup.game),
						Webloop::WebString(usetup.password),
						Webloop::WebBool(usetup.allow_new_players.value)
					), {}, &GameConnection::login_done);
		} // }}}
	}; // }}}
	struct USetup {	// Userdata setup, read from config file. {{{
		std::string url;
		std::string websocket;
		std::string game;
		std::string login;
		std::string password;
		Usetup() {
			// Read info from file. This is supposed to happen only once.
			std::ifstream cfg(userdata_config.userdata.value);
			while (cfg.is_open()) {
				std::string line;
				std::getline(cfg, line);
				if (!cfg.is_open())
					break;
				auto stripped = strip(line);
				if (stripped.empty() || stripped[0] == '#')
					continue;
				auto kv = split(line, 1, 0, "=");
				if (kv.size() != 2) {
					WL_log("ignoring invalid line in userdata config: " + stripped);
					continue;
				}
				for (int i = 0; i < 2; ++i)
					kv[i] = strip(kv[i]);
				if (kv[0] == "url") url = kv[1];
				else if (kv[0] == "websocket") websocket = kv[1];
				else if (kv[0] == "game") game = kv[1];
				else if (kv[0] == "login") login = kv[1];
				else if (kv[0] == "password") password = kv[1];
				else WL_log("ignoring invalid line in userdata config: " + stripped);
			}
			cfg.close();
		}
	}; // }}}
private:
	USetup usetup;
	Webloop::Httpd <PlayerConnection, Userdata> httpd;
	GameConnection local;
	std::shared_ptr <Webloop::WebMap> db_config;
	std::shared_ptr <Webloop::WebMap> player_config;
	int next_channel;
	std::map <std::string, PlayerConnection *> pending_gcid;
	std::map <std::string, PlayerConnection *> active_gcid;
	ConnectedCb connected_cb;
	DisconnectedCb disconnected_cb;
	void disconnect(PlayerConnection *connection) { // {{{
		// call closed callback on Player.
		auto YieldFrom(unused, (connection->*disconnected)());
	} // }}}
public:
	std::map <int, Player> players;
	void set_connected_cb(ConnectedCb cb) { connected_cb = cb; }
	void set_disconnected_cb(ConnectedCb cb) { disconnected_cb = cb; }
	Userdata( // {{{
			std::string const &service,
			std::shared_ptr <Webloop::WebMap> db_config,
			std::shared_ptr <Webloop::WebMap> player_config,
			std::string const &html_dirname = "html",
			Webloop::Loop *loop = nullptr,
			int backlog = 5
	) :
			usetup(),
			httpd(this, service, html_dirname, loop, backlog),
			local(usetup.userdata_websocket, this),
			db_config(db_config),
			player_config(player_config),
			clients(),
			next_channel(1),
			players()
	{
		usetup.default_userdata = Webloop.rstrip(usetup.default_userdata);

		/* Read translations. TODO {{{
		global system_strings, game_strings_html, game_strings_python
		// System translations.
		langfiles = importlib.resources.files(__package__).joinpath('lang')
		print('lang', langfiles)
		system_strings = {}
		pofiles = []
		for lang in langfiles.iterdir():
			if not lang.name.endswith(os.extsep + 'po'):
				continue
			print('parsing stings for "%s"' % lang)
			system_strings[os.path.splitext(os.path.basename(lang))[0]] = parse_translation(lang.read_bytes())

		// Game translations.
		dirs = fhs.read_data('lang', dir = True, multiple = True, opened = False)
		game_strings_html = {}
		game_strings_python = {}
		for d in dirs:
			s = read_translations(os.path.join(d, 'html'))
			game_strings_html.update(s)
			s = read_translations(os.path.join(d, 'python'))
			game_strings_python.update(s)
		// }}} */

		assert(!userdata_config.default_userdata.value.empty() || userdata_config.allow_local.value);	// If default is "", allow-local must be true.
	} // }}}
}; // }}}

template <class Player> std::map <std::string, Webloop::RPC <Userdata <Player>::GameConnection>::Published> Userdata <Player>::GameConnection::published;

// vim: set foldmethod=marker :

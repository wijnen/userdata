'use strict';
// login.js: code for logging in to game on userdata.

var server;
var server_config;
var selection;
var players;
var strings = {};
var is_managed;

function _(message) {
	var template;
	if (strings[message] === undefined)
		template = message;
	else
		template = strings[message];
	var args = arguments;
	return template.replaceAll(/\$([1-9])/g, function(match, num) {
		return args[num];
	});
}

function open_websocket() {
	var opened = function() {
		// connected.
		document.body.AddClass('connected');

		// If logout is requested, clear cookies.
		if (search.logout) {
			SetCookie('userdata_name', null);
			SetCookie('userdata_password', null);
		}

		// If credentials are in a cookie, use them.
		if (cookie.userdata_name !== undefined && cookie.userdata_password !== undefined) {
			if (is_managed)
				server.call('login_player', [cookie.userdata_name, cookie.userdata_password], {}, managed_reply);
			else {
				server.call('login_user', [0, cookie.userdata_name, cookie.userdata_password], {}, play_reply);
			}
		}
		else
			document.getElementById('name').focus();
		if (!is_managed) {
			// Remote login; enable registration button if allowed.
			server.call('get_settings', [], {}, function(config) {
				server_config = config;
				if (server_config['allow-new-users'])
					document.getElementById('register').removeClass('hidden');
			});
		}
	};
	var closed = function() {
		// disconnected.
		document.body.RemoveClass('connected');
		server = null;
	};
	var Connection = {
		translations: function(strs) { strings = strs; }
	};
	server = Rpc(Connection, opened, closed);
}

window.AddEvent('load', function() {
	is_managed = search.dcid !== undefined;
	if (is_managed) {
		// Managed player login.
		// Disallow managing data from here.
		document.body.AddClass('managed');

		// Enable registration button if allowed.
		if (search['allow-new-players'])
			document.getElementById('register').removeClass('hidden');
	}
	else if (search.url === undefined) {
		// "Manual" user login; request is not from game.
		// TODO: Support "direct" logins for data management.
		alert(_('Direct logins are not supported yet.'));
		return;
	}
	else {
		// External user login.
		document.body.RemoveClass('managed');
	}
	open_websocket();
});

function manage(p) { // {{{
	document.getElementById('login').AddClass('hidden');
	document.getElementById('manage_ui').RemoveClass('hidden');
	players = p;
	selection = [];
	var change = function() {
		var player = document.getElementById('player').selectedIndex;
		if (player == 0) {
			document.getElementById('playername').RemoveClass('hidden');
			for (var o = 0; o < selection.length; ++o) {
				if (selection[o][0].selectedItem == 0 && selection[o][1].value == '') {
					// Invalid selection; disable submit button.
					document.getElementById('select').disabled = true;
					return;
				}
			}
		}
		else {
			document.getElementById('playername').AddClass('hidden');
		}
		// Valid selection; enable submit button.
		document.getElementById('select').disabled = false;
	};
	var player_element = document.getElementById('player');
	player_element.AddEvent('change', change);
	player_element.AddElement('option').AddText('Add New');
	for (var p = 0; p < players.length; ++p) {
		var player = players[p];
		var option = player_element.AddElement('option').AddText(player.fullname + ' (' + player.name + ')');
		if (player.is_default)
			option.selected = true;
	}
	change();
} // }}}

function connect_reply(new_dcid) {
	window.parent.postMessage(new_dcid, '*');
}

function play_reply(success) { // {{{
	if (!success) {
		alert(_('Failed to log in'));
		return;
	}

	server.call('list_players', [0, search.url], {}, function(players) {

		var default_player;
		if (players.length == 1)
			default_player = players[0].name;
		else {
			for (var p = 0; p < players.length; ++p) {
				if (players[p].is_default) {
					default_player = players[p].name;
					break;
				}
			}
		}

		// If no record was found, fall back to management interface.
		if (default_player === undefined)
			return manage(players);

		// Connect to game with given settings.
		server.call('connect', [0, search.url, {gcid: search.gcid}, default_player], {}, connect_reply);
	});
} // }}}

function login_reply(success) { // {{{
	if (!success) {
		alert(_('Failed to log in'));
		return;
	}
	document.getElementById('login').AddClass('hidden');
	document.getElementById('manage_ui').RemoveClass('hidden');
	server.call('list_players', [0, search.url], {}, manage);
} // }}}

function managed_reply(success) { // {{{
	if (!success) {
		alert('Failed to log in');
		return;
	}
	document.getElementById('login').AddClass('hidden');
	document.getElementById('manage_ui').AddClass('hidden');
} // }}}

function log_in(event) {
	var name = document.getElementById('name').value;
	var password = document.getElementById('password').value;
	if (event.submitter.name == 'register') { // {{{
		// Register new user.
		// Name must be username:email.
		var r = name.match(/([^:]+):\s*(.+@.+?)\s*$/);
		if (!r)
			alert(_('For registration, name must be <username:email-address>'));
		else {
			var response = function(error) {
				if (error === null) {
					alert(_('Registration of user $1 succeeded. You can now log in.', r[1]));
					document.getElementById('name').value = r[1];
					document.getElementById('password').value = '';
					document.getElementById('password').focus();
				}
				else {
					alert('Registration of user ' + r[1] + ' failed: ' + error);
				}
			};
			if (!is_managed)
				server.call('register_user', [r[1], r[1], r[2], password], {}, response);
			else
				server.call('register_managed_player', [r[1], r[1], r[2], password], {}, response);
		}
	} // }}}
	if (is_managed) {
		if (event.submitter.name != 'register') {
			// Managed player login.
			server.call('login_player', [name, password], {}, managed_reply);
		}
	}
	else if (event.submitter.name == 'login') {
		// Manage game data.
		server.call('login_user', [0, name, password], {}, login_reply);
	}
	else if (event.submitter.name == 'play') {
		// Run with default settings.
		server.call('login_user', [0, name, password], {}, play_reply);
	}
	else if (event.submitter.name == 'register') {
		// Register new user.
		// Name must be username:email.
		var r = name.match(/([^:]+):\s*(.+@.+?)\s*$/);
		if (!r)
			alert(_('For registration, name must be <username:email-address>'));
		else {
			server.call('register_user', [r[1], r[1], r[2], password], {}, function(success) {
				if (success) {
					alert(_('Registration of user $1 succeeded. You can now log in.', r[1]));
					document.getElementById('name').value = r[1];
					document.getElementById('password').value = '';
					document.getElementById('password').focus();
				}
				else {
					alert(_('Registration of user $1 failed.', r[1]));
				}
			});
		}
	}
	else if (event.submitter.name == 'select') {
		// Already logged in, run with selected player, possibly creating it.
		var player_element = document.getElementById('player');
		if (player_element.selectedIndex == 0) {
			var playername = document.getElementById('playername').value;
			// Use name as full name by default; can be changed in management interface.
			server.call('add_player', [0, search.url, playername, playername, true], {}, function() {
				server.call('connect', [0, search.url, {gcid: search.gcid}, playername], {}, connect_reply);
			});
		}
		else {
			server.call('connect', [0, search.url, {gcid: search.gcid}, players[player_element.selectedIndex - 1].name], {}, connect_reply);
		}
	}
	else {
		console.error('Unexpected submit button used:', event.submitter.name);
	}
	return false;
}

function store() {
	SetCookie('userdata_name', document.getElementById('name').value);
	SetCookie('userdata_password', document.getElementById('password').value);
}

// vim: set foldmethod=marker :

'use strict';

var server;
var selection;
var players;

window.AddEvent('load', function() {
	document.getElementById('name').focus();
	if (search.game === undefined) {
		// "Manual" user login; request is not from game.
	}
	var opened = function() {
		// connected.
		document.body.AddClass('connected');
	};
	var closed = function() {
		// disconnected.
		document.body.RemoveClass('connected');
	};
	server = Rpc(null, opened, closed);
});

function log_in(event) {
	var manage = function(p) {
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
	};

	var play_reply = function(success) {
		if (!success) {
			alert('Failed to log in');
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
			server.call('connect', [0, search.url, {token: search.id}, default_player]);
		});
	};

	var login_reply = function(success) {
		if (!success) {
			alert('Failed to log in');
			return;
		}
		document.getElementById('login').AddClass('hidden');
		document.getElementById('manage').RemoveClass('hidden');
		server.call('list_players', [0, search.url], {}, manage);
	}

	var name = document.getElementById('name').value;
	var password = document.getElementById('password').value;
	if (event.submitter.name == 'login') {
		// Manage game data.
		server.call('login_user', [0, name, password], {}, login_reply);
	}
	else if (event.submitter.name == 'play') {
		// Run with default settings.
		server.call('login_user', [0, name, password], {}, play_reply);
	}
	else if (event.submitter.name == 'select') {
		// Already logged in, run with selected player, possibly creating it.
		var player_element = document.getElementById('player');
		if (player_element.selectedIndex == 0) {
			var playername = document.getElementById('playername').value;
			// Use name as full name by default; can be changed in management interface.
			server.call('add_player', [0, search.url, playername, playername, true], {}, function() {
				server.call('connect', [0, search.url, {token: search.id}, playername]);
			});
		}
		else
			server.call('connect', [0, search.url, {token: search.id}, players[player_element.selectedIndex - 1].name]);
	}
	else {
		console.error('unexpected submit button used:', event.submitter.name);
	}
	return false;
}

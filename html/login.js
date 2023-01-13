'use strict';

var server;
var selection;
var options;
var players;

window.AddEvent('load', function() {
	console.info(search);
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
		var slots = document.getElementById('slots').ClearAll();
		var containers = search.containers.split('\t');
		var container_obj = {};
		for (var c = 0; c < containers.length; ++c)
			container_obj[containers[c]] = true;
		server.call('list_containers', [0], {}, function(opts) {
			options = opts;
			selection = [];
			var change = function() {
				var player = document.getElementById('player').selectedIndex;
				if (player == 0) {
					document.getElementById('playername').RemoveClass('hidden');
					var newplayer = document.getElementById('newplayer');
					newplayer.RemoveClass('hidden');
					if (newplayer.value == '') {
						// Invalid player name; disable submit button.
						document.getElementById('select').disabled = true;
						return;
					}
					for (var o = 0; o < selection.length; ++o) {
						if (selection[o][0].selectedItem == 0 && (selection[o][1].value == '' || container_obj[selection[o][1].value])) {
							// Invalid selection; disable submit button.
							document.getElementById('select').disabled = true;
							return;
						}
					}
				}
				else {
					document.getElementById('playername').AddClass('hidden');
					document.getElementById('newplayer').AddClass('hidden');
				}
				// Valid selection; enable submit button.
				document.getElementById('select').disabled = false;
			};
			var player_element = document.getElementById('player');
			player_element.AddEvent('change', change);
			player_element.AddElement('option').AddText('Add New');
			for (var p = 0; p < players.length; ++p) {
				var player = players[p];
				var option = player_element.AddElement('option').AddText(player.player + ' (' + player.containers.join(', ') + ')');
				if (player.is_default)
					option.selected = true;
			}
			for (var c = 0; c < containers.length; ++c) {
				var tr = slots.AddElement('tr');
				tr.AddElement('th').AddText(containers[c]);
				var select = tr.AddElement('td').AddElement('select');
				select.AddElement('option').AddText('Add New');
				console.info(options);
				for (var o = 0; o < options.length; ++o) {
					select.AddElement('option').AddText(options[o].name);
				}
				var input = tr.AddElement('td').AddElement('input');
				selection.push([select, input]);
				select.AddEvent('change', change);
				input.AddEvent('change', change);
			}
			change();
		});
	};

	var play_reply = function(success) {
		if (!success) {
			alert(error);
			return;
		}

		server.call('list_players', [0, search.url], {}, function(players) {

			// Find record with containers to use.
			var default_player;
			if (players.length == 1)
				default_player = players[0].player;
			else {
				for (var p = 0; p < players.length; ++p) {
					if (players[p].is_default) {
						default_player = players[p].player;
						break;
					}
				}
			}

			// If no record was found, fall back to management interface.
			if (default_player === undefined)
				return manage(players);

			// Connect to game with given containers.
			server.call('connect', [0, search.url, {token: search.id}, default_player]);
		});
	};

	var login_reply = function(success) {
		if (!success) {
			alert(error);
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
		// Run with default containers.
		server.call('login_user', [0, name, password], {}, play_reply);
	}
	else if (event.submitter.name == 'select') {
		// Already logged in, run with selected player, possibly creating it.
		var player_element = document.getElementById('player');
		if (player_element.selectedIndex == 0) {
			var containers = [];
			for (var o = 0; o < selection.length; ++o) {
				if (selection[o][0].selectedIndex == 0)
					containers.push(selection[o][1].value);
				else
					containers.push(options[selection[o][0].selectedIndex - 1].name);
			}
			var playername = document.getElementById('playername').value;
			server.call('add_player', [0, playername, search.url, containers, true], {}, function() {
				server.call('connect', [0, search.url, {token: search.id}, playername]);
			});
		}
		else
			server.call('connect', [0, search.url, {token: search.id}, players[player_element.selectedIndex - 1].player]);
	}
	else {
		console.error('unexpected submit button used:', event.submitter.name);
	}
	return false;
}

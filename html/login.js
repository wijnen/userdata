'use strict';

var server;

window.AddEvent('load', function() {
	if (search.game === undefined) {
		// "Manual" user login; request is not from game.
	}
	if (search.allow_local) {
		// Local login is supported.
	}
	if (search.allow_remote) {
		// Remote login is supported.
	}
	if (search['default'] === undefined) {
		// There is no default.
	}
	// Options (depending on above settings):
	// - Forced default: connect to default server.
	// - Optional default: start with default server dialog, press confirm to connect, "choose server" for alternative
	// - No default: start with server selection
	var opened = function() {
		// connected.
		server.call('get_info', [], {}, function(info) {
			// TODO: update interface.
			document.body.AddClass('connected');
		});
	};
	var closed = function() {
		// disconnected.
		document.body.RemoveClass('connected');
	};
	server = Rpc(null, opened, closed);
});

function log_in(event) {
	console.info(event);
	var reply = function(error) {
		if (error !== null)
			alert(error);
		return;
	};
	var name = document.getElementById('name').value;
	var password = document.getElementById('password').value;
	if (event.submitter.name == 'register') {
		// Register new user.
		server.call('register', [name, password], {}, reply);
	}
	else {
		// Log in.
		server.call('login', [name, password], {}, reply);
	}
	return false;
}

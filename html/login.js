'use strict';

var server;

window.AddEvent('load', function() {
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

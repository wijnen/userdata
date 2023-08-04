"use strict";
// Code for in-game settings interface.
var server;
var Connection = {
	update_settings: function(settings) {
		document.getElementById('loginname').ClearAll().AddText(settings.loginname);
		document.getElementById('fullname').value = settings.fullname;
		document.getElementById('language').value = settings.language;
	}
	
};

function onopen() {
}

function onclose() {
}

window.AddEvent('load', function() {
	server = Rpc(Connection, onopen, onclose);
});

function change(event) {
	var name = document.getElementById('fullname').value;
	var language = document.getElementById('language').value;
	console.info('new settings', name, language);
	server.call('set_player_settings', [], {name: name, language: language});
	window.parent.postMessage(null, '*');
	return false;
}

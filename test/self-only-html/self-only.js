var game;
var msg;

window.AddEvent('load', function() {
	msg = document.getElementById('msg');
	game = Rpc({}, onopen, onclose);
});

function onopen() {
	msg.ClearAll().AddText('opened');
	game.call('get', [], {}, function(result) {
		msg.ClearAll().AddText('got ' + result);
	});
}

function onclose() {
	msg.ClearAll().AddText('closed');
}

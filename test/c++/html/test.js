var server;
var calls = {};

function opened() { console.info("connection to server opened"); }
function closed() { console.info("connection to server opened"); }

window.AddEvent('load', function() {
	server = Rpc(calls, opened, closed);
});

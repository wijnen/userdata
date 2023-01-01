var game;

window.AddEvent('load', function() {
	var userdata = document.getElementById('userdata');
	var msg = document.getElementById('msg');
	var callbacks = {
		setup: function(url) {
			console.info(url);
			var iframe = userdata.ClearAll().AddElement('iframe');
			iframe.src = url;
		},
		cheer: function() {
			msg.ClearAll().AddText('Success!');
		},
		fail: function() {
			msg.ClearAll().AddText('Failed!');
		}
	};
	game = Rpc(callbacks)
});

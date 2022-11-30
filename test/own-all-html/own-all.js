var game;

window.AddEvent('load', function() {
	var userdata = document.getElementById('userdata');
	var msg = document.getElementById('msg');
	var callbacks = {
		setup: function(config) {
			console.info(config);
			var iframe = userdata.ClearAll().AddElement('iframe');
			iframe.src = config['url'];
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

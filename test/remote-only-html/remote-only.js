window.AddEvent('load', function() {
	var msg = document.getElementById('msg');
	var callbacks = {
		userdata_setup: userdata_setup,
		cheer: function() {
			msg.ClearAll().AddText('Success!');
		},
		fail: function() {
			msg.ClearAll().AddText('Failed!');
		}
	};
	game = Rpc(callbacks)
});

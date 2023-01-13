function userdata_setup(default_url, game_url, containers, settings, id) {
	var userdata = document.getElementById('userdata');
	if (default_url == null) {
		// Connected to server; hide login screen.
		userdata.ClearAll();
		return;
	}
	// Build UI
	var form = userdata.ClearAll().AddElement('form');
	form.AddText('Userdata Address: ');
	var address = form.AddElement('input');
	address.value = default_url;
	address.type = 'text';
	var submit = form.AddElement('input');
	submit.type = 'submit';
	submit.value = 'Connect';
	var iframe = form.AddElement('iframe');
	if (address.value != '')
		iframe.src = address.value + '?url=' + encodeURIComponent(game_url) + '&containers=' + encodeURIComponent(containers.join('\t')) + '&id=' + encodeURIComponent(id);

	// Handle submit event.
	form.AddEvent('submit', function(event) {
		event.preventDefault();
		iframe.src = address.value + '?url=' + encodeURIComponent(game_url) + '&containers=' + encodeURIComponent(containers.join('\t')) + '&id=' + encodeURIComponent(id);
		return false;
	});
}

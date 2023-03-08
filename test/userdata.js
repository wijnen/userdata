"use strict";

// This file allows a project to show a userdata server selection and connect to a userdata.
// No other files are required in the project's source (except builders.js and rpc.js).

// To use:
// - When the connection is needed (probably on the window load event), set up an
//   Rpc object as usual.
// - In the callbacks object, set 'userdata_setup' to the function
//   userdata_setup, defined in this file.

function userdata_setup(default_url, game_url, settings, id, token) {
	var userdata = document.getElementById('userdata');

	// If this is a notification that connection between game and userdata is established: hide window. {{{
	if (game_url === null) {
		userdata.ClearAll();
		userdata.style.display = 'none';
		if (window.connected !== undefined)
			window.connected();
		return;
	} // }}}

	// Set default for game_url. {{{
	if (game_url == '')
		game_url = document.location.protocol + '//' + document.location.host + document.location.pathname;
	// }}}

	// Create userdata frame and set style. {{{
	var form = userdata.ClearAll().AddElement('form');
	userdata.style.display = 'block';
	userdata.style.position = 'fixed';
	userdata.style.left = '0px';
	userdata.style.top = '0px';
	userdata.style.right = '0px';
	userdata.style.bottom = '0px';
	userdata.style.boxSizing = 'border-box';
	userdata.style.background = 'white';
	userdata.style.padding = '1em 2em';
	userdata.style.margin = '3em 3em 3em 3em';
	userdata.style.border = 'solid black 2px';
	userdata.style.borderRadius = '2ex';
	userdata.style.minHeight = '10em';
	userdata.style.overflow = 'auto';
	// }}}
	// Create server selection. {{{
	var address;
	if (settings['allow-other']) {
		var store = form.AddElement('button').AddText('Store server details in cookie');
		store.type = 'button';
		store.style.display = 'block';
		store.style.float = 'right';
		store.AddEvent('click', function() {
			if (use_external.checked) {
				if (address.value == '')
					alert('Please enter a userdata address to store in the cookie.');
				else
					SetCookie('userdata_address', address.value);
			}
			else
				SetCookie('userdata_address', '');
		});
		var userdata_select;
		var use_external;
		if (settings['allow-local']) {
			var label = form.AddElement('label');
			use_external = label.AddElement('input');
			use_external.type = 'checkbox';
			label.AddText('Use external userdata server');
			if (cookie.userdata_address !== undefined) {
				if (cookie.userdata_address != '')
					use_external.checked = true;
			}
			else if (cookie.userdata_address === undefined && default_url != '')
				use_external.checked = true;
			use_external.AddEvent('change', function() {
				if (use_external.checked) {
					userdata_select.style.display = 'block';
					new_server(address.value);
				}
				else {
					userdata_select.style.display = 'none';
					new_server(null);
				}
			});
		}
		else {
			// Create fake "input" to allow reading that the checkbox is checked.
			use_external = {checked: true};
		}
		userdata_select = form.AddElement('div');
		if (settings['allow-local'] && !use_external.checked)
			userdata_select.style.display = 'none';
		userdata_select.AddText('Userdata Address: ');
		address = userdata_select.AddElement('input');
		address.value = cookie.userdata_address === undefined ? default_url : decodeURIComponent(cookie.userdata_address);
		address.type = 'text';
		var submit = userdata_select.AddElement('input');
		submit.type = 'submit';
		submit.value = 'Connect';
	}
	else {
		// Allow checking for address.value; it is always set to "local server".
		address = {value: ''};
	}
	// }}}
	// Create server iframe. {{{
	var iframe = form.AddElement('iframe');
	iframe.style.marginTop = '1em';
	iframe.style.width = '100%';
	iframe.style.height = 'calc(100vh - 13em)';
	iframe.style.boxSizing = 'border-box';
	// }}}

	// Function for loading new server into iframe. {{{
	var new_server = function(address) {
		if (address === null) {
			// This is a player login on the local (to the game) userdata server.
			iframe.src = settings['local-userdata'] + '?token=' + encodeURIComponent(token);
		}
		else {
			// This is an external userdata server.
			iframe.src = address + '?url=' + encodeURIComponent(game_url) + '&id=' + encodeURIComponent(id) + (settings.logout ? '&logout=1' : '');
		}
	}; // }}} 
	// Load initial server if there is a default. {{{
	if (settings['allow-local'] && address.value == '')
		new_server(null);
	else if (address.value != '')
		new_server(address.value);
	// }}}
	// Handle submit event. {{{
	form.AddEvent('submit', function(event) {
		event.preventDefault();
		new_server(address.value);
		return false;
	}); // }}}
}

// vim: set foldmethod=marker :

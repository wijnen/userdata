"use strict";

// This file allows a project to show a userdata server selection and connect to a userdata.
// No other files are required in the project's source (except builders.js and rpc.js).

// To use:
// - When the connection is needed (probably on the window load event), set up an
//   Rpc object as usual.
// - In the callbacks object, set 'userdata_setup' to the function
//   userdata_setup, defined in this file.

function userdata_setup(default_url, game_url, settings, id) {
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
	userdata.style.width = 'calc(100% - 6em)';
	userdata.style.height = 'calc(100% - 6em)';
	userdata.style.boxSizing = 'border-box';
	userdata.style.background = 'white';
	userdata.style.padding = '1em 2em';
	userdata.style.border = 'solid black 2px';
	userdata.style.borderRadius = '2ex';
	userdata.style.minHeight = '10em';
	userdata.style.overflow = 'auto';
	// }}}
	// Create server selection. {{{
	var div = form.AddElement('div');
	div.AddText('Userdata Address: ');
	var address = div.AddElement('input');
	address.value = default_url;
	address.type = 'text';
	var submit = div.AddElement('input');
	submit.type = 'submit';
	submit.value = 'Connect';
	// }}}
	// Create server iframe. {{{
	var iframe = form.AddElement('iframe');
	iframe.style.marginTop = '1em';
	iframe.style.width = '100%';
	iframe.style.height = 'calc(100vh - 12em)';
	iframe.style.boxSizing = 'border-box';
	// }}}

	// Function for loading new server into iframe. {{{
	var new_server = function(address) {
		iframe.src = address + '?url=' + encodeURIComponent(game_url) + '&id=' + encodeURIComponent(id);
	}; // }}} 
	// Load initial server if there is a default. {{{
	if (address.value != '')
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

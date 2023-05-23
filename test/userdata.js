"use strict";

// This file allows a project to show a userdata server selection and connect to a userdata.
// No other files are required in the project's source (except builders.js and rpc.js).

// To use:
// - When the connection is needed (probably on the window load event), set up an
//   Rpc object as usual.
// - In the callbacks object, set 'userdata_setup' to the function
//   userdata_setup, defined in this file.

window.AddEvent('load', function() {
	if (window.Connection === undefined)
		window.Connection = {};
	if (window.opened === undefined)
		window.opened = null;
	if (window.closed === undefined)
		window.closed = null;

	var menu_visible = false;
	var menudiv;
	window.AddEvent('keydown', function(event) {
		if (event.key != 'Escape')
			return;
		menu_visible = !menu_visible;
		if (menu_visible) {
			// Rebuild and show menu.
			var ul = menudiv.ClearAll().AddElement('ul');
			ul.style.paddingLeft = '0px';
			for (var m = 0; m < window.menu.length; ++m) {
				if (window.menu[m].enabled === false)
					continue;
				if (window.menu[m].action === null) {
					ul.AddElement('li').AddText(window.menu[m].text);
				}
				else {
					var button = ul.AddElement('li').AddElement('button').AddText(window.menu[m].text).AddEvent('click', function() {
						// Hide menu.
						menu_visible = false;
						menudiv.style.display = 'none';
						// Perform action.
						this.action();
					});
					button.type = 'button';
					button.action = window.menu[m].action;
				}
			}
		}
		menudiv.style.display = (menu_visible ? 'block' : 'none');
	});

	window.Connection.userdata_setup = function(default_url, game_url, settings, id, token) {
		// Find userdata login div; create new if it does not exist (the usual case). {{{
		var userdata = document.getElementById('userdata');
		if (userdata === null) {
			userdata = document.body.AddElement('div');
			userdata.id = 'userdata';
		}
		// }}}

		// Find userdata menu div; create new if it does not exist (the usual case). {{{
		menudiv = document.getElementById('userdata_menu');
		if (menudiv === null) {
			menudiv = document.body.AddElement('div');
			menudiv.id = 'userdata_menu';
		}
		// Create menu div and set style.
		menudiv.ClearAll();
		menudiv.style.display = 'none';
		menudiv.style.position = 'fixed';
		menudiv.style.top = '50vh';
		menudiv.style.left = '50vw';
		menudiv.style.padding = '1em 2em';
		menudiv.style.background = 'white';
		menudiv.style.border = 'solid black 2px';
		menudiv.style.boxSizing = 'border-box';
		menudiv.style.borderRadius = '2ex';
		menudiv.style.minHeight = '10em';
		menudiv.style.overflow = 'auto';
		menudiv.style.transform = 'translate(-50%, -50%)';
		menudiv.style.marginRight = '-50%';
		// }}}

		if (window.menu === undefined)
			window.menu = [];

		var menu_continue = function() {
		};
		var menu_change = function() {
			// TODO.
		};
		var menu_logout = function() {
			window.server.call('userdata_logout');
		};
		// Default menu options:
		// - login name
		// - Continue

		// - Change Name
		// - Logout
		if (window.menu_title === undefined)
			window.menu_title = {text: '', action: null, enabled: true};
		if (window.menu.length == 0 || window.menu[1].text != 'Continue') {
			window.menu.splice(0, 0,
				window.menu_title,
				{text: 'Continue', action: menu_continue, enabled: true},
			);
			window.menu.push(
				//{text: 'Change Name', action: menu_change, enabled: true}, TODO
				{text: 'Logout', action: menu_logout, enabled: true}
			);
		}

		// If this is a notification that connection between game and userdata is established: hide window. {{{
		if (game_url === null) {
			userdata.ClearAll();
			window.menu_title.text = 'Logged in as ' + settings.name + (settings.managed_name !== null ? ' (' + settings.managed_name + ')' : '');
			window.menu_title.enabled = true;
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
				if (cookie !== undefined) {
					if (cookie.userdata_address !== undefined) {
						if (cookie.userdata_address != '')
							use_external.checked = true;
					}
					else if (cookie.userdata_address === undefined && default_url != '')
						use_external.checked = true;
				}
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
				iframe.src = settings['local-userdata'] + '?token=' + encodeURIComponent(token) + (settings['allow-new-players'] ? '&allow-new-players=1' : '') + (settings.logout ? '&logout=1' : '');
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
	};

	console.info('connecting');
	window.server = Rpc(window.Connection, window.opened, window.closed);
	window.server.reconnect = function() {
		console.info('reconnecting');
		var reconnect = window.server.reconnect;
		window.server = Rpc(window.Connection, window.opened, window.closed);
		window.server.reconnect = reconnect;
	};
});

// vim: set foldmethod=marker :

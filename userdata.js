"use strict";

// File documentation. {{{

// This file allows a project to show a userdata server selection and connect to a userdata.
// No other files are required in the project's source (except builders.js and rpc.js).

// To use, just include this file as a script source in the html header.
// This file will make sure a connection to the server is made. Calls to the
// server over this connection can be made using the server variable.

// Some optional objects can be defined:
// - The Connection object defines all callbacks that the server can make.
// - The opened function is called when the connection with the server is made.
// - The closed function is called when the connection with the server is lost.
// - The menu object contains menu entries. Each entry is an object with attributes enabled, action, text. Some default options are added on the window load event.
// - The menu_title object is an entry for the menu title. This is automatically updated on login.
// - The update_strings function should be defined to update all translations (including for menu strings). This is called when a new language is selected by the player.
// All these objects get a default definition if they were not defined.

// If DOM object with id userdata or userdata_menu are defined, those are used
// instead of adding new divs to the DOM tree.

// }}}

// Translations. {{{
// The argument to this function should be a literal string. Calls to it are
// detected as translatable text.
// This function replaces the string with the translation in the currently
// selected language.
// If the message contains $1 .. $9, those are replaced with the value from the extra arguments to this function.
function _userdata_translate(message) {
	var template;
	if (!this)
		template = message;
	else if (this[message] === undefined) {
		console.warn('String to be translated not found in dictionary:', message)
		template = message;
	}
	else
		template = this[message];
	var args = arguments;
	return template.replaceAll(/\$([1-9])/g, function(match, num) {
		return args[num];
	});
}

function _() {
	return _userdata_translate.apply(window._userdata_program_strings, arguments);
}
// }}}

var userdata_menu_visible = false;
var userdata_menudiv;

function userdata_rebuild_menu() { // {{{
	var ul = userdata_menudiv.ClearAll().AddElement('ul');
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
				userdata_menu_visible = false;
				userdata_menudiv.style.display = 'none';
				// Perform action.
				this.action();
			});
			button.type = 'button';
			button.action = window.menu[m].action;
		}
	}
} // }}}

window.AddEvent('message', function(event) {
	var host = /([a-z]+:\/\/[^\/]+)/.exec(userdata.iframe_address);
	if (host === null || event.origin != host[1]) {
		console.error('Invalid message origin:', event.origin, '!=', userdata.iframe_address);
		return;
	}
	if (event.data === null) {
		// Settings window requests to be closed.
		userdata.settings_visible = false;
		userdata.ClearAll();
		userdata.style.display = 'none';
	}
	else {
		// event.data is the dcid that can be used for changing settings.
		window.userdata_dcid = event.data;
	}
});

window.AddEvent('load', function() {
	// Set variable defaults. {{{
	if (window.Connection === undefined)
		window.Connection = {};
	if (window.opened === undefined)
		window.opened = null;
	if (window.closed === undefined)
		window.closed = null;
	// }}}

	var translatable = document.getElementsByClassName('translate');
	for (var e = 0; e < translatable.length; ++e)
		translatable[e].source_text = translatable[e].textContent;

	// The menu popup. {{{
	window.AddEvent('keydown', function(event) {
		if (event.key != 'Escape')
			return;
		if (userdata.settings_visible) {
			userdata.settings_visible = false;
			userdata.ClearAll();
			userdata.style.display = 'none';
			return;
		}
		userdata_menu_visible = !userdata_menu_visible;
		if (userdata_menu_visible)
			userdata_rebuild_menu();
		userdata_menudiv.style.display = (userdata_menu_visible ? 'block' : 'none');
	});
	// }}}

	window.Connection.userdata_setup = function(default_url, game_url, settings, gcid, dcid) { // {{{
		// Find userdata login div; create new if it does not exist (the usual case). {{{
		// default_url is the default location to load into the iframe.
		// game_url is the url passed to an external userdata for it to connect to the game.
		// settings contains game settings.
		// gcid is passed to the game by the userdata so the game knows which connection has logged in.
		// dcid is an identifier for managed players only, to identify to the userdata which connection this is.
		var userdata = document.getElementById('userdata');
		if (userdata === null) {
			userdata = document.body.AddElement('div');
			userdata.id = 'userdata';
		}
		if (dcid !== undefined)
			userdata.dcid = dcid;
		// }}}

		// Find userdata menu div; create new if it does not exist (the usual case). {{{
		userdata_menudiv = document.getElementById('userdata_menu');
		if (userdata_menudiv === null) {
			userdata_menudiv = document.body.AddElement('div');
			userdata_menudiv.id = 'userdata_menu';
		}
		// Create menu div and set style.
		userdata_menudiv.ClearAll();
		userdata_menudiv.style.display = 'none';
		userdata_menudiv.style.position = 'fixed';
		userdata_menudiv.style.top = '50vh';
		userdata_menudiv.style.left = '50vw';
		userdata_menudiv.style.padding = '1em 2em';
		userdata_menudiv.style.background = 'white';
		userdata_menudiv.style.border = 'solid black 2px';
		userdata_menudiv.style.boxSizing = 'border-box';
		userdata_menudiv.style.borderRadius = '2ex';
		userdata_menudiv.style.minHeight = '10em';
		userdata_menudiv.style.overflow = 'auto';
		userdata_menudiv.style.transform = 'translate(-50%, -50%)';
		userdata_menudiv.style.marginRight = '-50%';
		// }}}

		// Set up menu. {{{
		var translate = function() { return _userdata_translate.apply(window._userdata_module_strings, arguments); };
		if (window.menu === undefined)
			window.menu = [];

		var menu_continue = function() {
		};
		var menu_settings = function() {
			// Open settings in iframe.
			userdata.settings_visible = true;
			userdata.iframe = userdata.ClearAll().AddElement('iframe');
			userdata.iframe.style.width = '100%';
			userdata.iframe.style.height = '100%';
			userdata.iframe.style.boxSizing = 'border-box';
			userdata.iframe.src = userdata.iframe_address + '/settings.html?settings=' + encodeURIComponent(userdata.dcid);
			userdata.style.display = 'block';
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
		if (window.menu_continue === undefined)
			window.menu_continue = {text: '', action: menu_continue, enabled: true};
		if (window.menu_logout === undefined)
			window.menu_logout = {text: '', action: menu_logout, enabled: true};
		if (window.menu_settings === undefined)
			window.menu_settings = {text: '', action: menu_settings, enabled: true};
		if (!window.menu.default_options_defined) {
			window.menu.default_options_defined = true;
			window.menu.splice(0, 0,
				window.menu_title,
				window.menu_continue,
			);
			window.menu.push(
				window.menu_settings,
				window.menu_logout
			);
		}
		// Always update button text, because language may have changed.
		window.menu_continue.text = translate('Continue');
		window.menu_settings.text = translate('Settings');
		window.menu_logout.text = translate('Logout');
		// }}}

		// If this is a notification that connection between game and userdata is established: hide window. {{{
		if (game_url === null) {
			userdata.ClearAll();
			userdata.style.display = 'none';
			if (settings.managed === null)
				window.menu_title.text = translate('Logged in as $1 (external)', settings.name);
			else
				window.menu_title.text = translate('Logged in as $1 (login name: $2)', settings.name, settings.managed);
			window.menu_title.enabled = true;
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
		userdata.iframe = form.AddElement('iframe');
		userdata.iframe.style.marginTop = '1em';
		userdata.iframe.style.width = '100%';
		userdata.iframe.style.height = 'calc(100vh - 13em)';
		userdata.iframe.style.boxSizing = 'border-box';
		// }}}

		// Function for loading new server into iframe. {{{
		var new_server = function(address) {
			if (address === null) {
				// This is a player login on the local (to the game) userdata server.
				userdata.iframe_address = settings['local-userdata'];
				userdata.iframe.src = userdata.iframe_address + '/login.html?dcid=' + encodeURIComponent(userdata.dcid) + (settings['allow-new-players'] ? '&allow-new-players=1' : '') + (settings.logout ? '&logout=1' : '');
			}
			else {
				// This is an external userdata server.
				userdata.iframe_address = address;
				userdata.iframe.src = userdata.iframe_address + '/login.html?url=' + encodeURIComponent(game_url) + '&gcid=' + encodeURIComponent(gcid) + (settings.logout ? '&logout=1' : '');
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
	}; // }}}

	if (window.update_strings === undefined)
		window.update_strings = function() {};
	window.Connection.userdata_translate = function(module_strings, program_strings) { // {{{
		window._userdata_module_strings = module_strings;
		window._userdata_program_strings = program_strings;
		for (var e = 0; e < translatable.length; ++e)
			translatable[e].ClearAll().AddText(_(translatable[e].source_text));
		window.update_strings();
		if (userdata_menu_visible)
			userdata_rebuild_menu();
	}; // }}}

	//console.info('connecting');
	window.server = Rpc(window.Connection, window.opened, window.closed);
	window.server.reconnect = function() { // {{{
		//console.info('reconnecting');
		var reconnect = window.server.reconnect;
		window.server = Rpc(window.Connection, window.opened, window.closed);
		window.server.reconnect = reconnect;
	}; // }}}
});

// vim: set foldmethod=marker :

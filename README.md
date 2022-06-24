# Userdata
This system allows programs to store data for their users without implementing
it. The target audience is games, but it is usable for any program that stores data. In this documentation, the words _game_ and _program_ are used interchangably.

# Project Goals

1. Allow users full control over their data. When a program uses this system, users can host their own userdata instance to store its data. This way they can be confident the host will not profile them by combining several data sources. Note that malicious hosts will always be able to store their own copy and do this anyway; this system does not protect against this. It does protect against large leaks from hacks though, because if there is no central server holding data for many users, that server also cannot be hacked.
2. Allow sites to host a game without using the resources to store the players' data.

# Typical Use Cases

1. Users can log in to manage their games and grant or revoke permissions from games to their data. They can also view and modify their data if they want, and download or restore a backup.
1. Simple data storage. The game connects to a userdata that is configured into it (probably through a commandline argument). It logs in using credentials it has, and can immediately use the data. If the game supports multiple players, it handles this by itself. Players never see that the game uses this system.
1. Remote (although it can be on the same host) data storage. The handshake for this is that the site optionally asks the player for a userdata host (alternatively it requires one). Then it connects to that host and requests a login url. It sends the url to the browser, which uses it to log in to the host. Then the game is allowed to use the data.

# State of the project

Working components:

- Data storage
- Simple login using a password
- Remote login using a token and a password

Still to be done:

- Complex WHERE clauses
- Simple login using a public/private key pair
- User data management interface

# Contact

In case of any feedback, please contact [Bas Wijnen <wijnen@debian.org>](mailto:wijnen@debian.org).

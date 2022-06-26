# Userdata
This system allows programs to store data for their users without implementing
it. The target audience is games, but it is usable for any program that stores data. In this documentation, the words _game_ and _program_ are used interchangably.

# Project Goals

1. Allow users full control over their data. When a program uses this system, users can host their own userdata instance to store its data. This way they can be confident the host will not profile them by combining several data sources. Note that malicious hosts will always be able to store their own copy and do this anyway; this system does not protect against this. It does protect against large leaks from hacks though, because if there is no central server holding data for many users, that server also cannot be hacked.
2. Allow sites to host a game without using the resources to store the players' data.

# Typical Use Cases

1. Users can log in to manage their games and grant or revoke permissions from games to their data. They can also view and modify their data if they want, and download or restore a backup.
1. Single player storage. The game connects to a userdata that is configured into it (probably through a commandline argument). It logs in using credentials it has, and can immediately use the data. The game does not support multiple players. The player never sees that the game uses this system.
1. Remote (although it can be on the same host) storage. The handshake for this is that the site optionally asks the player for a userdata host (alternatively it requires one). Then it connects to that host and requests a login url. It sends the url to the browser, which uses it to log in to the host. Then the game is allowed to use the data.
1. Multi player storage. At boot, the game first logs in using credentials for user G. It also uses this for its own data. When a new player connects, it optionally allows them to choose a different userdata host. The game requests a login url from the userdata (either its own, or the one requested by the player) and sends the browser there. The player logs in (as user P). If the default host is used, the data is stored under user G. However, user G is not allowed access to user P's password (but of course the database owner can always access everything that is stored in the database). If enabled by the game (usually throuhg a commandline option), the player can choose a different userdata host to connect to. If they do, the data is stored under user P on that host (user G is not known there). For the game, there is no difference other than the url it uses to connect to the userdata. (This means the system returns an object to the game which handles the details of using user G or a different host.)

# Game Configuration Options

- Userdata host
- Game credentials
- Whether playhers are allowed to choose a different userdata host (for multi player storage, this can be stored in the game's storage)

# State of the project

Working components:

- Data storage
- Single player login using a password
- Multi player remote login using a token and a password

Still to be done:

- Complex WHERE clauses
- Single player login using a public/private key pair
- User data management interface
- Multi player local login
- Providing interface to game for accessing user data

# Contact

Feedback of any kind is appreciated. Please send it to [Bas Wijnen &lt;wijnen@debian.org&gt;](mailto:wijnen@debian.org?subject=Userdata%20feedback).

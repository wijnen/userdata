#include "userdata.hh"

using namespace Webloop;

class Player {
	void connected_cb() {
	}
	void disconnected_cb() {
	}
};

int main(int argc, char **argv) {
	auto game_db = WebMap::create({"table", WebMap::create({"field", "value"})});
	auto player_db = WebMap::create();
	Userdata <Player> userdata("5592", game_db, player_db);
	Loop::get()->run();
	return 0;
}

#include "userdata.hh"

using namespace Webloop;

class Player {
	Userdata <Player> *userdata;
public:
	static coroutine create(Player *&player, Userdata <Player>::PlayerConnection &connection) { // {{{
		player = new Player();
		player->userdata = connection.get_userdata();
		co_return WN();
	} // }}}
	static coroutine started(Userdata <Player> *data) { // {{{
		auto field = WV("field");
		auto tf = WV("table", field);
		auto coro = data->game_data.fgcall("select", tf);
		auto result = YieldFrom(coro);
		auto vr = result->as_vector();
		if (vr->size() < 1) {
			YieldFrom(data->game_data.fgcall("insert", WV("table", WM(WT("field", "Change Me!")))));
		}
		co_return WN();
	} // }}}
	coroutine call(std::string const &target, Args args, KwArgs kwargs) { // {{{
		std::cerr << "called: " << target << args->print() << " / " << kwargs->print() << std::endl;
		if (target == "set") {
			assert(args->size() == 1 && (*args)[0]->get_type() == WebObject::STRING);
			YieldFrom(userdata->game_data.fgcall("update", WV(
							"table",
							WM(WT("field", (*args)[0])),
							WV()
						)));
		}
		else if (target == "get") {
			assert(args->size() == 0);
			co_return YieldFrom(userdata->game_data.fgcall("select", WV("table", WV("field"))));
		}
		co_return WN();
	} // }}}
};

int main(int argc, char **argv) { // {{{
	(void)&argc;
	try {
		Webloop::init(argv);
		auto game_db = WM(WT("table", WV(WV("field", "text DEFAULT NULL"))));
		auto player_db = WM();
		Userdata <Player> userdata("7000", game_db, player_db);
		std::cerr << "running" << std::endl;
		Loop::get()->run();
	}
	catch (char const *msg) {
		std::cerr << "crash: " << msg << std::endl;
	}
	return 0;
} // }}}

// vim: set foldmethod=marker :

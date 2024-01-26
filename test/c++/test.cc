#include "userdata.hh"

using namespace Webloop;

struct Base {
	typedef coroutine (Base::*Published)(Args args, KwArgs kwargs);
	typedef coroutine (Base::*PublishedFallback)(std::string const &target, Args args, KwArgs kwargs);
	static coroutine create(Base *&player, Userdata <Base>::PlayerConnection &connection);
	static coroutine started(Userdata <Base> *data);
	std::map <std::string, Published> *published;
	PublishedFallback published_fallback;
};

class Player : public Base {
public:
	typedef coroutine (Player::*Published)(Args args, KwArgs kwargs);
	Userdata <Base> *userdata;
	static std::map <std::string, Base::Published> player_published;
	Player() {
		WL_log("created player");
		published = &player_published;
		published_fallback = nullptr;
	}
	coroutine set(Args args, KwArgs kwargs) { // {{{
		(void)&kwargs;
		assert(args->size() == 1 && (*args)[0]->get_type() == WebObject::STRING);
		YieldFrom(userdata->game_data.fgcall("update", WV(
						"table",
						WM(WT("field", (*args)[0])),
						WV()
					)));
		co_return WN();
	} // }}}
	coroutine get(Args args, KwArgs kwargs) { // {{{
		(void)&kwargs;
		assert(args->size() == 0);
		co_return YieldFrom(userdata->game_data.fgcall("select", WV("table", WV("field"))));
	} // }}}
};

std::map <std::string, Base::Published> Player::player_published = {
	{"get", reinterpret_cast <Base::Published>(&Player::get)},
	{"set", reinterpret_cast <Base::Published>(&Player::set)}
};

class Alternate : public Base {
public:
	typedef coroutine (Alternate::*Published)(Args args, KwArgs kwargs);
	static std::map <std::string, Base::Published> alternate_published;
	Alternate() {
		WL_log("created alternate");
		published = &alternate_published;
		published_fallback = nullptr;
	}
	coroutine call(Args args, KwArgs kwargs) { // {{{
		std::cerr << "alternate called: " << args->print() << " / " << kwargs->print() << std::endl;
		co_return WN();
	} // }}}
};

std::map <std::string, Base::Published> Alternate::alternate_published = {
	{"call", reinterpret_cast <Base::Published>(&Alternate::call)},
};

coroutine Base::create(Base *&player, Userdata <Base>::PlayerConnection &connection) { // {{{
	switch (connection.get_index()) {
	case 1:
	{
		Alternate *p = new Alternate();
		player = p;
		break;
	}
	default:
	{
		Player *p = new Player();
		player = p;
		p->userdata = connection.get_userdata();
		break;
	}
	}
	co_return WN();
} // }}}

coroutine Base::started(Userdata <Base> *data) { // {{{
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

int main(int argc, char **argv) { // {{{
	(void)&argc;
	try {
		Webloop::init(argv);
		auto game_db = WM(WT("table", WV(WV("field", "text DEFAULT NULL"))));
		auto player_db = WM();
		Userdata <Base> userdata(game_db, player_db);
		std::cerr << "running" << std::endl;
		Loop::get()->run();
	}
	catch (char const *msg) {
		std::cerr << "crash: " << msg << std::endl;
	}
	return 0;
} // }}}

// vim: set foldmethod=marker :
